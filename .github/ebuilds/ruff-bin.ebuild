# Copyright 2026 Gentoo Authors
# Distributed under the terms of the GNU General Public License v2

EAPI=8

DESCRIPTION="An extremely fast Python linter and code formatter, written in Rust"
HOMEPAGE="https://docs.astral.sh/ruff/"

MY_P="ruff-x86_64-unknown-linux-gnu"
SRC_URI="https://github.com/astral-sh/ruff/releases/download/${PV}/${MY_P}.tar.gz -> ${P}.tar.gz"
S="${WORKDIR}/${MY_P}"

LICENSE="MIT"
SLOT="0"
KEYWORDS="amd64"
RESTRICT="mirror strip"

RDEPEND="!dev-util/ruff"

QA_PREBUILT="usr/bin/ruff"

src_install() {
	dobin ruff
}
