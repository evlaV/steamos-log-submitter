#!/bin/bash
#
#  SPDX-License-Identifier: LGPL-2.1+
#
#  Copyright (c) 2022 Valve.
#  Maintainer: Guilherme G. Piccoli <gpiccoli@igalia.com>
#
#  This is the kdump log pre-processing, part of the SteamOS log
#  submission machinery. This script performs some parsing on
#  kdump/pstore collected data and fills some relevant request
#  fields that are part of the agreed API with Valve's servers.
set -e


#  Helper function to print error outputs for this add-on.
#  Arg1: detailed error text.
err_addon() {
	logger "steamos-kdump-addon: $1"
}

#  Next function determines the serial number if we are
#  running on Steam Deck - otherwise, sets it to 0. The
#  routine is executed only once, it bails on re-execution.
SERIAL_NUM=""
get_serial_number() {
if [ "${SERIAL_NUM}" != "" ]; then
	return
fi

SERIAL_NUM=0
PNAME="$(dmidecode -s system-product-name)"
if [ "${PNAME}" = "Jupiter" ]; then
	SERIAL_NUM="$(dmidecode -s system-serial-number)"
fi
}


ADDON_BASE_FOLDER="/home/.steamos/offload/var/kdump/"
KDUMP_LOGS_FLD="${ADDON_BASE_FOLDER}/logs"
KDUMP_TMP_FLD="${ADDON_BASE_FOLDER}/.tmp"
PENDING_FLD="${ADDON_BASE_FOLDER}/pending"

#  Iterate over all unprocessed logs.
#  TODO(?): despite we have a loop here, we should really have a single
#  log per reboot, at most. Hence, we don't even track multiple potential
#  log blobs in the kdump .tmp folder. This might or not change...
for log in "${KDUMP_LOGS_FLD}"/*.zip; do
	CURR_NAME="$(basename "${log}" ".zip")"
	if [ ! -s "${log}" ]; then
		err_addon "skipping empty file: ${CURR_NAME}.zip"
		continue
	fi

	get_serial_number
	#  Notice that STEAM_ACCOUNT is inherited from the
	#  parent script, that runs this add-on.
	NEW_NAME="steamos-${CURR_NAME}_${SERIAL_NUM}-${STEAM_ACCOUNT}.zip"

	#  Fill the mandatory and some optional fields. For that, rely on
	#  the ".tmp" folder created (and kept) by the kdump/pstore tool.

	if [ ! -d "${KDUMP_TMP_FLD}" ]; then
		err_addon "no kdump tmp folder, skipping ${CURR_NAME}"
		continue
	fi

	#  Create a temp. file that is required in order to fill the fields.
	CRASH_SUMMARY="${KDUMP_TMP_FLD}/crash_summary"
	SED_EXPR="/Kernel panic \-/,/Kernel Offset\:/p"
	sed -n "${SED_EXPR}" "${KDUMP_TMP_FLD}"/dmesg* > "${CRASH_SUMMARY}"
	sync "${CRASH_SUMMARY}"
	STACK_SED_EXPR="/ Call Trace\:/,/ RIP\:/p"

	REQ_STACK="$(sed -n "${STACK_SED_EXPR}" "${CRASH_SUMMARY}" | sed "1d")"
	REQ_NOTE="$(cat "${CRASH_SUMMARY}")"
	REQ_PRODUCT="holo"
	REQ_HAS_BLOB=1

	#  Finally, produce the companion file.
	COMPANION="${PENDING_FLD}/.${NEW_NAME}"
	mkdir -p "${PENDING_FLD}"
	touch "${COMPANION}"

	{
		echo "REQ_HAS_BLOB=${REQ_HAS_BLOB}"
		echo "REQ_PRODUCT=\"${REQ_PRODUCT}\""
		echo "REQ_NOTE=\"${REQ_NOTE}\""
		echo "REQ_STACK=\"${REQ_STACK}\""
	} >> "${COMPANION}"

	if [ ! -s "${COMPANION}" ]; then
		err_addon "couldn't create companion file: ${COMPANION}"
		continue
	fi

	#  Finally, move the log file to the proper path, with the new name.
	mv "${log}" "${PENDING_FLD}/${NEW_NAME}"
	sync "${PENDING_FLD}/${NEW_NAME}"
	rm -rf "${KDUMP_TMP_FLD}"
done
