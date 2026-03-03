{
  pkgs,
  lib,
  config,
  inputs,
  ...
}:

{
  # https://devenv.sh/basics/
  env.GREET = "devenv";

  # Playwright — use Nix-managed browsers, skip pip download
  env.PLAYWRIGHT_BROWSERS_PATH = "${pkgs.playwright.browsers}/share/playwright";
  env.PLAYWRIGHT_DRIVER_EXECUTABLE_PATH = "${pkgs.playwright-driver}/bin/playwright-driver";
  env.PLAYWRIGHT_SKIP_VALIDATE_HOST_REQUIREMENTS = true;
  env.PLAYWRIGHT_NODEJS_PATH = "${pkgs.nodejs}/bin/node";
  env.PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD = "1";

  # https://devenv.sh/packages/
  packages = [
    pkgs.git
    pkgs.uv
    pkgs.playwright
    pkgs.playwright-driver
    pkgs.playwright.browsers
    pkgs.nodejs
  ];

  # https://devenv.sh/languages/
  # languages.rust.enable = true;
  languages = {
    python = {
      enable = true;
      version = "3.14";
      venv.enable = true;
      uv.enable = true;
    };
  };

  # https://devenv.sh/processes/
  # processes.cargo-watch.exec = "cargo-watch";

  # https://devenv.sh/services/
  # services.postgres.enable = true;

  # https://devenv.sh/scripts/
  scripts.hello.exec = ''
    echo hello from $GREET
  '';
  scripts.start-graph.exec = ''
    python -m graph "$@"
  '';
  scripts.test-graph.exec = ''
    python -m pytest tests/ -q --ignore=tests/e2e "$@"
  '';
  scripts.test-e2e.exec = ''
    python -m pytest tests/e2e/ -v "$@"
  '';

  enterShell = ''
    hello
    git --version
  '';

  # https://devenv.sh/tasks/
  # tasks = {
  #   "myproj:setup".exec = "mytool build";
  #   "devenv:enterShell".after = [ "myproj:setup" ];
  # };

  # https://devenv.sh/tests/
  enterTest = ''
    echo "Running tests"
    git --version | grep --color=auto "${pkgs.git.version}"
  '';

  # https://devenv.sh/pre-commit-hooks/
  # pre-commit.hooks.shellcheck.enable = true;

  # See full reference at https://devenv.sh/reference/options/
}
