# Do not edit this file manually. It is automatically generated.
# Edit 'capture-all.sh' instead.

stage_dir "stage-without-init"

expect_exec -oh6 "TPS version 1.1" "" "Usage: tps <command> <arguments>..." "" "Available commands:" "show" -eempty -r 1 tps
expect_exec -oempty -eh "Error: File 'scripts/internal/tps_init.sh' not found." -r 2 tps show

stage_dir "stage-with-init"

expect_exec -oh6 "TPS version 1.1" "" "Usage: tps <command> <arguments>..." "" "Available commands:" "show" -eempty -r 1 tps
expect_exec -oh "The variable is 'the_init_value'." -eempty tps show