prefix     := /usr

libdir     := $(prefix)/lib

localstatedir := /home/.steamos/offload/var

systemdunitsdir := $(shell pkg-config --define-variable=prefix=$(prefix) --variable=systemdsystemunitdir systemd 2>/dev/null \
			  || echo $(libdir)/systemd/system/)
udevdir := $(shell pkg-config --define-variable=prefix=$(prefix) --variable=udevdir udev 2>/dev/null \
			  || echo $(libdir)/udev/)
sysctldir := $(shell pkg-config --define-variable=prefix=$(prefix) --variable=sysctldir systemd 2>/dev/null \
			  || echo $(libdir)/sysctl.d/)
sysusersdir := $(shell pkg-config --define-variable=prefix=$(prefix) --variable=sysusersdir systemd 2>/dev/null \
			  || echo $(libdir)/sysusers.d/)
tmpfilesdir := $(shell pkg-config --define-variable=prefix=$(prefix) --variable=tmpfilesdir systemd 2>/dev/null \
			  || echo $(libdir)/udev/)

infiles := \
	base.cfg \
	systemd/sysusers.conf \
	systemd/tmpfiles.conf

all:

clean:
	rm -f $(infiles)

%: %.in
	@sed \
		-e "s;@LOCALSTATEDIR@;$(localstatedir);g" \
		$< > $@

install: all $(infiles)
	install -D -m0644 systemd/steamos-log-submitter.service $(DESTDIR)$(systemdunitsdir)/steamos-log-submitter.service
	install -D -m0644 systemd/steamos-log-submitter.timer $(DESTDIR)$(systemdunitsdir)/steamos-log-submitter.timer
	install -D -m0644 systemd/sysusers.conf $(DESTDIR)$(sysusersdir)/steamos-log-submitter.conf
	install -D -m0644 systemd/tmpfiles.conf $(DESTDIR)$(tmpfilesdir)/steamos-log-submitter.conf
	install -D -m0644 systemd/crash-hook.sysctl $(DESTDIR)$(sysctldir)/60-crash-hook.conf
	install -D -m0644 udev/80-gpu-crash.rules $(DESTDIR)$(udevdir)/80-gpu-crash.rules
	install -D -m0644 base.cfg $(DESTDIR)$(libdir)/steamos-log-submitter/base.cfg
	install -D -m0755 crash-hook.py $(DESTDIR)$(libdir)/steamos-log-submitter/crash-hook.py
