prefix     := /usr

libdir     := $(prefix)/lib

systemdunitsdir := $(shell pkg-config --define-variable=prefix=$(prefix) --variable=systemdsystemunitdir systemd 2>/dev/null \
			  || echo $(libdir)/systemd/system/)
udevdir := $(shell pkg-config --define-variable=prefix=$(prefix) --variable=udevdir udev 2>/dev/null \
			  || echo $(libdir)/udev/)
sysusersdir := $(shell pkg-config --define-variable=prefix=$(prefix) --variable=sysusersdir systemd 2>/dev/null \
			  || echo $(libdir)/sysusers.d/)
tmpfilesdir := $(shell pkg-config --define-variable=prefix=$(prefix) --variable=tmpfilesdir systemd 2>/dev/null \
			  || echo $(libdir)/udev/)
all:

install: all
	install -D -m0644 systemd/steamos-log-submitter.service $(DESTDIR)$(systemdunitsdir)/steamos-log-submitter.service
	install -D -m0644 systemd/steamos-log-submitter.timer $(DESTDIR)$(systemdunitsdir)/steamos-log-submitter.timer
	install -D -m0644 udev/80-gpu-crash.rules $(DESTDIR)$(udevdir)/80-gpu-crash.rules
	install -D -m0644 tmpfiles.d/steamos-log-submitter.conf $(DESTDIR)$(tmpfilesdir)/steamos-log-submitter.conf
	install -D -m0644 sysusers.d/steamos-log-submitter.conf $(DESTDIR)$(sysusersdir)/steamos-log-submitter.conf
