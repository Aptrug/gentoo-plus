# Distributed under the terms of the GNU General Public License v2

EAPI=8

DESCRIPTION="Vim, an improved vi-style text editor (pure minimal live)"
HOMEPAGE="https://www.vim.org https://github.com/vim/vim"
inherit vim-doc bash-completion-r1
SRC_URI="https://github.com/vim/vim/archive/refs/tags/v${PV}.tar.gz -> ${P}.tar.gz"
RESTRICT="mirror"

LICENSE="vim"
SLOT="0"
# IUSE="+vim-pager"
IUSE=""
KEYWORDS="amd64"

RDEPEND=">=sys-libs/ncurses-5.2-r2:0="

DEPEND="${RDEPEND}"

pkg_setup() {
	unset LANG LC_ALL
	export LC_COLLATE="C"
}

src_configure() {
	econf \
		--disable-rightleft \
		--disable-arabic \
		--disable-netbeans \
		--disable-xattr \
		--disable-smack \
		--disable-sysmouse \
		--disable-libsodium \
		--disable-xsmp \
		--disable-xsmp-interact \
		--disable-largefile \
		--enable-gui=no \
		--without-x \
		--without-wayland \
		--disable-terminal \
		--disable-autoservername \
		--disable-darwin \
		--disable-luainterp \
		--disable-perlinterp \
		--disable-pythoninterp \
		--disable-rubyinterp \
		--disable-tclinterp \
		--disable-mzschemeinterp \
		--disable-acl \
		--disable-gpm \
		--disable-nls \
		--disable-canberra \
		--disable-selinux \
		--disable-cscope
}

src_compile() {
	emake -C src auto/osdef.h objects
	emake
}

src_install() {
	dobin src/vim src/xxd/xxd
	emake -C src \
		installruntime \
		installmanlinks \
		DESTDIR="${D}" \
		BINDIR="${EPREFIX}"/usr/bin \
		MANDIR="${EPREFIX}"/usr/share/man \
		DATADIR="${EPREFIX}"/usr/share || die
	newbashcomp "${FILESDIR}"/vim-completion vim
}

pkg_postinst() {
	update_vim_helptags
}

pkg_postrm() {
	update_vim_helptags
}
