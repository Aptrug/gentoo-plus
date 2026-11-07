# Copyright 2026 Gentoo Authors
# Distributed under the terms of the GNU General Public License v2

EAPI=8

DESCRIPTION="Limine bootloader - UEFI x86_64 EFI binary"
HOMEPAGE="https://limine-bootloader.org/"

MY_P="limine-binary"
SRC_URI="https://github.com/Limine-Bootloader/Limine/releases/download/v${PV}/${MY_P}.tar.xz"
S="${WORKDIR}/${MY_P}"

LICENSE="BSD-2"
SLOT="0"
KEYWORDS="amd64"
RESTRICT="mirror strip"

src_install() {
	insinto /boot/EFI/limine
	doins BOOTX64.EFI
}
