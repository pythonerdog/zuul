#!/bin/sh

echo $*
case "$1" in
    fetch)
	echo "Fake git error"
	exit 1
	;;
    version)
        echo "git version 1.0.0"
        exit 0
        ;;
esac
