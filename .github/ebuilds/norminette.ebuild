# Copyright 2026 Gentoo Authors
# Distributed under the terms of the GNU General Public License v2

EAPI=8

DISTUTILS_USE_PEP517=setuptools
DISTUTILS_UPSTREAM_PEP517=standalone
PYTHON_COMPAT=( python3_10 )

inherit distutils-r1

DESCRIPTION="C linter for 42 Network"
HOMEPAGE="https://github.com/42School/norminette"
SRC_URI="https://github.com/42School/norminette/archive/refs/tags/${PV}.tar.gz -> ${P}.tar.gz"
S="${WORKDIR}/${PN}-${PV}"

LICENSE="MIT"
SLOT="0"
KEYWORDS="amd64"

python_prepare_all() {
	rm -rf "${S}/pdf" || die
	distutils-r1_python_prepare_all
}

python_install_all() {
	distutils-r1_python_install_all
	cat > "${T}/norminette" <<-EOF || die
		#!/bin/sh
		exec "${EPREFIX}/usr/bin/python3" -m norminette "\$@"
	EOF
	dobin "${T}/norminette"
}
