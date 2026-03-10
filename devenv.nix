{ pkgs, ... }:
{
  packages = [
    pkgs.git
    pkgs.uv
  ];

  languages.python = {
    enable = true;
    version = "3.14";
    venv.enable = true;
    uv = {
      enable = true;
      sync.enable = true;
      sync.allExtras = true;
    };
  };
}
