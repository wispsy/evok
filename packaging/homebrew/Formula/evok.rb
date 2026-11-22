class Evok < Formula
  include Language::Python::Virtualenv

  desc "Pure-Python high-performance package manager and virtualization runtime"
  homepage "https://github.com/wispsy/evok"
  url "https://files.pythonhosted.org/packages/source/e/evok/evok-0.1.0.tar.gz"
  sha256 "77a2ab2ee59ae6403feb48dc58a3d702794e44d0cdc0713c3ac0ee2fbda304a3"
  license "MIT"

  depends_on "python@3.14"

  def install
    virtualenv_install_with_resources
  end

  test do
    assert_match "evok 0.1.0", shell_output("#{bin}/ev --version")
    assert_match "evok 0.1.0", shell_output("#{bin}/evok --version")
    assert_match "evok version:", shell_output("#{bin}/ev info")
    system libexec/"bin/python", "-c", "import evok; assert evok.__version__ == '0.1.0'"
  end
end
