#!/bin/bash
#
#  SPDX-License-Identifier: LGPL-2.1+
#
#  Copyright (c) 2022 Valve.
#  Author: Guilherme G. Piccoli <gpiccoli@igalia.com>
#
#  This is the SteamOS Log Submitter (SLS) infrastructure. It
#  sends data from many log collecting tools to Valve servers.
set -e


#  Global settings
SLS_FOLDER="/home/.steamos/offload/var/steamos-log-submit/"
SLS_SCRIPTS_DIR="/usr/lib/steamos-log-submitter/scripts.d/"

#  Valve servers URLs
START_URL="https://api.steampowered.com/ICrashReportService/StartCrashUpload/v1"
FINISH_URL="https://api.steampowered.com/ICrashReportService/FinishCrashUpload/v1"
#  TODO: the URLs are hardcoded for now; should we make the above
#  settings user-configurable?

#  Global variables (used here but may be also used inside the
#  add-on/scripts, for the log name).
LOG_SUBMITTED=0
STEAM_ACCOUNT=0
STEAM_ID=0
ADDON_NAME=""


#  Helper function to print error outputs.
#  Arg1: detailed error text.
err_print() {
	logger "steamos-log-submitter: $1, aborting..."
}

#  The following function is used to get Steam Account/ID from the VDF
#  file for the regular user (UID 1000); in case it fails, STEAM_ID
#  and STEAM_ACCOUNT variables aren't updated.
get_steam_account_id() {
	#  Step 1: determine the current user's /home folder. Notice
	#  that UID_MIN = 1000, UID_MAX = 60000 from "/etc/login.defs",
	#  but getent takes a long time to check all of that, so let's
	#  restrict to UID = 1000 only.
	HOMEFLD="$(getent passwd 1000 | cut -f6 -d:)"

	#  Let's determine the VDF file location using the above info.
	LOGINVDF="${HOMEFLD}/.local/share/Steam/config/loginusers.vdf"
	if [ ! -s "${LOGINVDF}" ]; then #  bail if no valid VDF is found.
		return
	fi

	#  Step 2: Parse the VDF file to obtain Account/ID; the following AWK
	#  command was borrowed from: https://unix.stackexchange.com/a/663959.
	NUMREG=$(grep -c AccountName "${LOGINVDF}")
	IDX=1
	while [ ${IDX} -le "${NUMREG}" ]; do
		MR=$(awk -v n=${IDX} -v RS='}' 'NR==n{gsub(/.*\{\n|\n$/,""); print}' "${LOGINVDF}" | grep "MostRecent" | cut -f4 -d\")
		if [ "$MR" -ne 1 ]; then
			IDX=$((IDX + 1))
			continue
		fi

		STEAM_ACCOUNT=$(awk -v n=${IDX} -v RS='}' 'NR==n{gsub(/.*\{\n|\n$/,""); print}' "${LOGINVDF}" | grep "AccountName" | cut -f4 -d\")

		#  Get also the Steam ID, used in the POST request to Valve
		#  servers; this is a bit fragile, but there's no proper VDF
		#  parse tooling it seems...
		LN=$(grep -n "AccountName.*${STEAM_ACCOUNT}\"" "${LOGINVDF}" | cut -f1 -d:)
		LN=$((LN - 2))
		STEAM_ID=$(sed -n "${LN}p" "${LOGINVDF}" | cut -f2 -d\")
		break
	done
}

#  Next function is the main routine for log submission; it implements
#  Valve's API through POST/PUT requests. It returns and logs on systemd
#  journal in case of errors - otherwise, finishes quietly.
submit_log() {
	#  Files used during the POST/PUT requests construction.
	CURL_ERR="${SLS_FOLDER}/.curl_err-${ADDON_NAME}-${REQ_TIME}"
	RESPONSE_FILE="${SLS_FOLDER}/.curl_response-${ADDON_NAME}-${REQ_TIME}"
	CURL_PUT_HEADERS="${SLS_FOLDER}/.curl_put_headers-${ADDON_NAME}-${REQ_TIME}"

	#  Status tracker for this log submission.
	LOG_SUBMITTED=0

	#  POST request - split it in many lines just for better readability.
	POST_REQ="steamid=${STEAM_ID}&have_dump_file=${REQ_HAS_BLOB}&dump_file_size=${REQ_BLOB_SZ}"
	POST_REQ="${POST_REQ}&product=${REQ_PRODUCT}&build=${REQ_BUILD}&version=${REQ_VERSION}"
	POST_REQ="${POST_REQ}&platform=${REQ_PLATFORM}&crash_time=${REQ_TIME}&stack=${REQ_STACK}"
	POST_REQ="${POST_REQ}&note=${REQ_NOTE}&format=json"
	if ! curl -X POST -d "${POST_REQ}" "${START_URL}" 1>"${RESPONSE_FILE}" 2>"${CURL_ERR}"; then
		err_print "curl issues - failed in the start POST (err=$?)"
		# keep "${RESPONSE_FILE}", as debug information
		return
	fi

	RESPONSE_PUT_URL="$(jq -r '.response.url' "${RESPONSE_FILE}")"
	RESPONSE_GID="$(jq -r '.response.gid' "${RESPONSE_FILE}")"

	# Construct the PUT request based on the POST response
	PUT_HEADERS_LEN=$(jq '.response.headers.pairs | length' "${RESPONSE_FILE}")

	# Validate the response headers; allow a maximum of 20 arguments for now...
	if [ "${PUT_HEADERS_LEN}" -le 0 ] || [ "${PUT_HEADERS_LEN}" -gt 20 ]; then
		err_print "unsupported number of response headers (${PUT_HEADERS_LEN})"
		# keep "${RESPONSE_FILE}", as debug information
		return
	fi

	LOOP_CNT=0
	while [ ${LOOP_CNT} -lt "${PUT_HEADERS_LEN}" ]; do
		NAME="$(jq -r ".response.headers.pairs[${LOOP_CNT}].name" "${RESPONSE_FILE}")"
		VAL="$(jq -r ".response.headers.pairs[${LOOP_CNT}].value" "${RESPONSE_FILE}")"

		echo "${NAME}: ${VAL}" >> "${CURL_PUT_HEADERS}"
		LOOP_CNT=$((LOOP_CNT + 1))
	done

	rm -f "${RESPONSE_FILE}"
	if ! curl -X PUT --data-binary "@${REQ_BLOB_PATH}" -H "@${CURL_PUT_HEADERS}"\
	 "${RESPONSE_PUT_URL}" 1>/dev/null 2>"${CURL_ERR}"; then
		err_print "curl issues - failed in request PUT (err=$?)"
		# keep "${CURL_PUT_HEADERS}", as debug information
		return
	fi

	if ! curl -X POST -d "gid=${RESPONSE_GID}" "${FINISH_URL}" 1>/dev/null 2>"${CURL_ERR}"; then
		err_print "curl issues - failed in the finish POST (err=$?)"
		# keep "${CURL_PUT_HEADERS}", as debug information
		return
	fi

	#  If we reached this point, the log should have been submitted
	#  succesfully to Valve servers.
	LOG_SUBMITTED=1
	rm -f "${CURL_PUT_HEADERS}"
	rm -f "${CURL_ERR}"
}


### START POINT of script execution ###

#  We require this folder for log submission.
mkdir -p "${SLS_FOLDER}"
if [ ! -d "${SLS_FOLDER}" ]; then
	err_print "issue creating SLS folder"
	exit 1
fi

get_steam_account_id
#  The POST request requires a valid Steam ID.
if [ "${STEAM_ID}" -eq 0 ]; then
	err_print "invalid Steam ID"
	exit 1
fi

#  Below is the logic for log submission. It is split in 3 steps:
#
#  (a) Check network connectivity. If we cannot access the internet, we
#  are doomed to fail, so bail-out quickly, since we retry more times later.
#
#  (b) Log pre-processing phase: here some customization is allowed.
#  Notice that many log collection tools might end-up using this log
#  submission infrastructure, so we enable them to perform some
#  particular operations on their logs, customize the filename and
#  override some request fields. This is done through script add-ons,
#  the log submission logic "orbits" around these scripts - for each
#  script, we have a set of log blobs to submit. Details about how this
#  works are described in comments along with the code doing it.
#
#  (c) Final stage, here we effectively perform the POST/PUT requests
#  to Valve servers, in a loop (per log blob). This step is intrinsically
#  connected to (b).
#
#  TODO: In step 2, still need to agree if we are embedding the add-on
#  scripts in this package, or if a third-party package can install
#  the pre-processing code like the sysctl.d/ approach. Based on the
#  (tentative) upstream Arch kdump, the best design seems the latter,
#  for example:
#
#    (upstream kdump)                (log submission tool)
#           |                                  |
#           |                                  |
#           =================|==================
#                            |
#              (steamos-kdump-customizations)
#
#  In the kdump case, we would have the "steamos-kdump-customizations"
#  package providing the add-on scripts for log pre-processing. Worth
#  notice that if we are doing this way, we are kinda estabilishing a
#  log submission API for packages, that can install "handlers" for
#  us to submit. On the other hand, would be much easier to keep everything
#  on the same code base - if we'd change the "API", quite easy to change
#  all the add-ons. Opinions are much appreciated on that matter!


### Step 1: network validation ###
LOOP_CNT=0
MAX_LOOP=5
TEST_URL="http://test.steampowered.com/204"

while [ ${LOOP_CNT} -lt ${MAX_LOOP} ]; do
	RES="$(curl -s -m 2 -I ${TEST_URL} | head -n1 | cut -f2 -d\ )"
	if [ "${RES}" = "204" ]; then
		break
	fi
	sleep 0.5
	LOOP_CNT=$((LOOP_CNT + 1))
done

# Bail out in case we have network issues.
if [ ${LOOP_CNT} -ge ${MAX_LOOP} ]; then
	err_print "network issues"
	exit 1
fi

### Step 2: log pre-processing / request fields filling ###
#
#  Details of the design: we have basically two loops, one
#  is the add-on/script loop, that iterates on all available
#  scripts. The scripts can be seen as the interested parties
#  in sending log blobs to Valve servers. Each add-on/script
#  is responsible to fill some mandatory parameters (the ADDON_
#  variables), to properly name the log blobs it wants to send
#  (moving them to the respective "<...>/pending folder") and
#  to generate one companion file per blob, which contains some
#  fields required by the sending process + some optionally
#  overriden fields.
#
#  The second loop then iterates through all log blobs available
#  on "${ADDON_PENDING_PATH}/" - each blob LOG_NAME has a companion
#  file .LOG_NAME generated by the add-on script, that contains the
#  required fields filled in the form of a shell script - it is
#  sourced here so we can perform the log submission.
#
#  So, in summary, we have 3 sets of variables:
#  [1] The add-on/script specific variables, sourced here once per-addon;
#  [2] The request fields that are mandatory per-file, generated by the add-on;
#  [3] The request fields that are optionally overriden by the add-on.
#
#  Below such fields are clearly distinguished. Be aware of that when
#  writing some add-on that makes use of this log submission mechanism,
#  it is a form of API that must be respected.

shopt -s nullglob
for script in "${SLS_SCRIPTS_DIR}"/*; do
	if [ ! -f "$script" ]; then
		continue
	fi

	#  Below variable is just used to name some temp files
	#  during the log submission routine.
	ADDON_NAME="$(basename "${script}")"

	#  This is the main folder that will enable us to seek logs
	#  to submit - it MUST be set by the script/add-on sourced above.
	ADDON_BASE_FOLDER="" # contains the "pending" and "uploaded" folders.

	#  The scripts do inherit the "nullglob" option, which is required
	#  when looping in potentially empty directories.
	. "${script}"

	ADDON_PENDING_PATH="${ADDON_BASE_FOLDER}/pending/"
	ADDON_UPLOADED_PATH="${ADDON_BASE_FOLDER}/uploaded/"

	for curr_log in "${ADDON_PENDING_PATH}"/*; do
		#  First of all, let's check if we have the companion file
		#  that provides the necessary information - if not, bail out.
		LOG_COMPANION="${ADDON_PENDING_PATH}/.$(basename "${curr_log}")"
		if [ ! -f "${LOG_COMPANION}" ]; then
			err_print "no companion file for ${curr_log}"
			continue
		fi

		#  So, the following variables are *mandatory* to be set by
		#  the companion file, or else things going to fail.
		REQ_HAS_BLOB=0
		REQ_PRODUCT="generic"

		#  The next ones are optional to be set in the companion
		#  file; if not set, the submission process doesn't fail,
		#  the default values are valid though maybe not ideal.
		REQ_BUILD="$(grep "BUILD_ID" "/etc/os-release" | cut -f2 -d=)"
		REQ_VERSION="$(uname -r)"
		REQ_PLATFORM="linux"
		REQ_STACK="generic"
		REQ_NOTE="generic log submission"

		#  Finally, next 3 variables shouldn't be touched by the
		#  companion file - we're gonna override them below anyway.
		REQ_TIME=0
		REQ_BLOB_SZ=0
		REQ_BLOB_PATH=""

		. "${LOG_COMPANION}"

		if [ "${REQ_HAS_BLOB}" -ne 0 ]; then
			REQ_BLOB_PATH="${curr_log}"
			REQ_BLOB_SZ="$(stat --printf="%s" "${REQ_BLOB_PATH}")"
		fi

		# Run the script and submit the log...
		REQ_TIME=$(date +"%s") # Current epoch, UTC timezone.
		submit_log

		if [ ${LOG_SUBMITTED} -ne 0 ]; then
			mkdir -p "${ADDON_UPLOADED_PATH}"
			mv "${REQ_BLOB_PATH}" "${ADDON_UPLOADED_PATH}"
			rm -f "${LOG_COMPANION}"
		fi
	done

	##  TODO: work here the log prune mechanism, based in some ADDON_
	##  variable that determines the maximum size of logs before pruning.
done
shopt -u nullglob
