FROM python:2.7.18-buster AS buster-2.7-ssh

ENV DEBIAN_FRONTEND noninteractive

RUN apt-get update \
  && apt-get install -y dumb-init openssh-server \
  && apt-get clean \
  && rm -rf /var/lib/apt/lists/*

RUN mkdir /var/run/sshd && chmod 0755 /var/run/sshd

# This may or not be required to allow logins by preventing pam_loginuid
# trying to write out audit level things that may not work in a container
RUN sed -ri 's/session(\s+)required(\s+)pam_loginuid.so/session\1optional\2pam_loginuid.so/' /etc/pam.d/sshd

RUN ssh-keygen -A -v

RUN ssh-keygen -t ed25519 -f /root/.ssh/id_ed25519

COPY authorized_keys /root/.ssh/authorized_keys
RUN chmod 0600 /root/.ssh/authorized_keys

ENTRYPOINT ["/usr/bin/dumb-init", "--"]
CMD ["/usr/sbin/sshd", "-D", "-o", "ListenAddress=0.0.0.0" ]
