# Makefile for Arch Smart Update Checker SELinux Policy
# SPDX-License-Identifier: GPL-3.0-or-later

TARGETS = asuc
MODULES = ${TARGETS:=.pp}

all: ${MODULES}

%.pp: %.te %.if %.fc
	@echo "Building $@ policy module"
	make -f /usr/share/selinux/devel/Makefile $@

install: ${MODULES}
	@echo "Installing SELinux policy modules"
	semodule -i ${MODULES}
	@echo "Restoring file contexts"
	restorecon -R /usr/bin/asuc-cli /usr/bin/asuc-gui 2>/dev/null || true
	restorecon -R /usr/lib/python*/site-packages/asuc 2>/dev/null || true
	@echo "SELinux policy installed successfully"

uninstall:
	@echo "Removing SELinux policy modules"
	semodule -r ${TARGETS} || true

clean:
	rm -f *.pp *.fc *.if *.te~
	rm -rf tmp/

relabel:
	@echo "Relabeling asuc files"
	restorecon -Rv /usr/bin/asuc-cli /usr/bin/asuc-gui
	restorecon -Rv /usr/lib/python*/site-packages/asuc
	restorecon -Rv ~/.config/asuc ~/.cache/asuc

.PHONY: all install uninstall clean relabel 