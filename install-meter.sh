#!/bin/bash
# Fresh-install integration for the previously deployed FIFO-only meter format.
set -Eeuo pipefail
src=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
source "$src/package-manager.sh"
[[ $EUID == 0 ]] || { echo 'Run as root.' >&2; exit 1; }
version=$(dpkg-query -W -f='${Version}' asl3-asterisk)
[[ -n $version ]] || { echo 'Installed ASL Asterisk version could not be determined.' >&2; exit 1; }
# Never silently compile against a different Asterisk ABI.
allmode_apt install -y "asl3-asterisk-dev=$version"
[[ $(dpkg-query -W -f='${Version}' asl3-asterisk) == "$version" &&
   $(dpkg-query -W -f='${Version}' asl3-asterisk-dev) == "$version" ]] || {
  echo 'Asterisk/header versions changed or do not match; meter build stopped.' >&2; exit 1;
}
module=$(dpkg-query -L asl3-asterisk-modules | awk '/\/modules\/format_sln\.so$/ {print}')
[[ $module == /*/format_sln.so && $module != *$'\n'* && -f $module ]] || {
  echo 'Cannot identify the installed Asterisk module directory.' >&2; exit 1;
}
work=$(mktemp -d)
trap 'rm -rf -- "$work"' EXIT
gcc -O2 -Wall -Wextra -Werror "$src/native-meter/test_fifo.c" -o "$work/test_fifo"
"$work/test_fifo"
gcc -shared -fPIC -O2 -Wall -Wextra -Werror -isystem /usr/include \
  "$src/native-meter/format_allmode_meter.c" -o "$work/format_allmode_meter.so"
install -m 0644 "$work/format_allmode_meter.so" "$(dirname -- "$module")/format_allmode_meter.so"
install -d -m 0755 /opt/allmode/native-meter
install -m 0644 "$src/native-meter/format_allmode_meter.c" "$src/native-meter/meter_fifo.h" /opt/allmode/native-meter/
printf 'Built for asl3-asterisk %s\n' "$version" > /opt/allmode/native-meter/BUILD.txt
chmod 0644 /opt/allmode/native-meter/BUILD.txt
echo "FIFO-only meter installed for ASL Asterisk $version. No radio service was started."
