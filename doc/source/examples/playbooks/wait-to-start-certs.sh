#!/bin/bash

# Zuul needs ssl certs to be present to talk to zookeeper before it
# starts.

wait_for_certs() {
    echo `date -Iseconds` "Wait for certs to be present"
    for i in $(seq 1 300); do
        # Introduced for 3.7.0: zookeeper shall wait for certificates to be available
        # examples_zk_1.examples_default.pem is the last file created by ./tools/zk-ca.sh
        [ -f /var/certs/keystores/examples_zk_1.examples_default.pem ] && return
        sleep 1
    done;

    echo `date -Iseconds` "Timeout waiting for certs"
    exit 1
}

wait_for_certs
