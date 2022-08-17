prefix     := /usr

libdir     := $(prefix)/lib

systemdunitsdir := $(shell pkg-config --define-variable=prefix=$(prefix) --variable=systemdsystemunitdir systemd 2>/dev/null \
			  || echo $(libdir)/systemd/system/)
all:

install: all
	install -D -m0644 steamos-log-submitter.service $(DESTDIR)$(systemdunitsdir)/steamos-log-submitter.service
	install -D -m0644 steamos-log-submitter.timer $(DESTDIR)$(systemdunitsdir)/steamos-log-submitter.timer
	install -D -m0755 submitter-load.sh $(DESTDIR)$(libdir)/steamos-log-submitter/submitter-load.sh
	install -D -m0755 submit-logs.sh $(DESTDIR)$(libdir)/steamos-log-submitter/submit-logs.sh
	install -D -m0755 kdump.sh $(DESTDIR)$(libdir)/steamos-log-submitter/scripts.d/kdump.sh
