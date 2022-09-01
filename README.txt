#  ###########################################################################
#  ####################### SteamOS Log Submitter (SLS) #######################
#  ###########################################################################
#
#  This is the generic infrastructure for log submission to Valve's servers.
#  By using SLS, other tools (like kdump) are able to submit error reports
#  to Valve in the Steam Deck system.
#
#  The usage is well-explained in the comments on "submit-logs.sh", but
#  basically it is required to have an add-on script in SLS scripts.d/
#  directory, that performs some (custom) operations in the logs and
#  generate some necessary information for log submission API. Such API
#  is described below in details.
#
#
#  TODOs
#  ###########################################################################
#  * Would be interesting to have a clean-up/auto-prune mechanism, to keep up
#  to N most recent log files (or up to N megabytes of logs), instead of
#  keeping all of them forever.
#
#  * VDF parsing would benefit from some improvement, it's at least "fragile"
#  for now, to be generous...but that seems a bit complicated.
#
#
#  LOG SUBMISSION INFORMATION
#  ###########################################################################
#  * The 'curl' tool is used to submit the requests to Valve servers; for
#  that, some temporary files named ".curl_XXX" are saved in the SLS
#  folder. These files are deleted if the log submission mechanism works fine,
#  or else they're currently kept for debug purposes, along with a new
#  ".curl_err" file.
#
#  * It is assumed that any throttling / anti-DoS mechanism comes from the
#  server portion, so SLS doesn't perform any significant validations with
#  this respect, only basic correctness validations.
#
#
#  => The API details: it works by a first POST request to Valve servers,
#  which, when succeed, returns 3 main components in the response. We use
#  these values to perform a PUT request with the compressed log blob, and
#  finally a last POST request is necessary to finish the transaction.
#  Below, see the specific format of such requests, using the kdump request
#  as an example - "product" is specially important to change in other log
#  add-ons, since it seems to be used to distinguish between log types:
#
#  The first POST takes the following fields:
#
#    steamid = user Steam ID, based on the latest Steam logged user;
#    have_dump_file = 0/1 - should be 1 when sending a log blob file;
#    dump_file_size = the file size, in bytes;
#    product = "holo";
#    build = the SteamOS build ID, from '/etc/os-release' file;
#    version = running kernel version;
#    platform = "linux" (hard-coded for now);
#    crash_time = the timestamp (epoch) of log collection/submission;
#    stack = a really concise call trace summary, only functions/addrs;
#    note = summary of the dmesg crash info, specifically a full stack trace;
#    format = "json" (hard-coded for now);
#
#  The response of a succeeding POST will have multiple fields, that can
#  be split in 3 categories:
#
#    PUT_URL = a new URL to be used in the PUT request;
#    GID = special ID used to finish the submission process in the next POST;
#    header name/value pairs = multiple pairs of name/value fields used as
#                              headers in the PUT request.
#
#  After parsing the response, we perform a PUT request to the PUT_URL, with
#  the log blob file as a "--data-binary" component and the additional headers
#  that were collected in the first POST's response. Finally, we just POST the
#  GID to the finish URL ("gid=GID_NUM") and the process is terminated.
#
#  Notice we heavily use 'jq' tool to parse the JSON response, so we assume
#  this format is the response one and that it's not changing over time.
