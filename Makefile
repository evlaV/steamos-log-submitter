prefix     := /usr

libdir     := $(prefix)/lib

systemdunitsdir := $(shell pkg-config --define-variable=prefix=$(prefix) --variable=systemdsystemunitdir systemd 2>/dev/null \
			  || echo $(libdir)/systemd/system/)
all:

install: all
	install -D -m0644 systemd/steamos-log-submitter.service $(DESTDIR)$(systemdunitsdir)/steamos-log-submitter.service
	install -D -m0644 systemd/steamos-log-submitter.timer $(DESTDIR)$(systemdunitsdir)/steamos-log-submitter.timer
