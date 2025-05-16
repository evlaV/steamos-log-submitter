prefix     := /usr

libdir     := $(prefix)/lib

localstatedir := /var

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
dbuspolicydir := $(shell pkg-config --define-variable=prefix=$(prefix) --variable=datadir dbus-1 2>/dev/null \
			  || echo $(prefix)/share)/dbus-1/system.d

infiles := \
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
	install -D -m0644 dbus/com.steampowered.SteamOSLogSubmitter.conf $(DESTDIR)$(dbuspolicydir)/com.steampowered.SteamOSLogSubmitter.conf
	install -D -m0644 systemd/steamos-log-submitter.service $(DESTDIR)$(systemdunitsdir)/steamos-log-submitter.service
	install -D -m0644 systemd/sysusers.conf $(DESTDIR)$(sysusersdir)/steamos-log-submitter.conf
	install -D -m0644 systemd/tmpfiles.conf $(DESTDIR)$(tmpfilesdir)/steamos-log-submitter.conf
	install -D -m0644 systemd/crash-hook.sysctl $(DESTDIR)$(sysctldir)/60-crash-hook.conf
	install -D -m0644 udev/steamos-log-submitter.rules $(DESTDIR)$(udevdir)/rules.d/79-steamos-log-submitter.rules
	install -D -m0644 base.cfg $(DESTDIR)$(libdir)/steamos-log-submitter/base.cfg
	install -D -m0644 LICENSE.txt $(DESTDIR)$(prefix)/share/licenses/steamos-log-submitter/LICENSE
	mkdir -p $(DESTDIR)$(systemdunitsdir)/multi-user.target.wants
	ln -sf $(systemdunitsdir)/steamos-log-submitter.service $(DESTDIR)$(systemdunitsdir)/multi-user.target.wants
