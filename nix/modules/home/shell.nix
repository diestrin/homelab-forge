{ pkgs, ... }:
{
  programs.zsh = {
    enable = true;
    enableCompletion = true;
    autosuggestion.enable = true;
    syntaxHighlighting.enable = true;

    oh-my-zsh = {
      enable = true;
      plugins = [
        "git"
        "direnv"
        "fzf"
        "dotenv"
      ];
      theme = "spaceship";
      # spaceship ships themes/ under share/zsh
      custom = "${pkgs.spaceship-prompt}/share/zsh";
    };

    sessionVariables = {
      SPACESHIP_TIME_SHOW = "true";
      SPACESHIP_DIR_TRUNC_REPO = "false";
      SPACESHIP_DIR_TRUNC = "3";
    };

    shellAliases = {
      # Preserve existing L1 prototype helpers (Phase 2 may supersede).
      dev-machine = "docker run -it --rm -v \"$PWD\":/workspace -v \"$HOME\"/.ssh:/root/.ssh -w /workspace dev-machine";
      dev-machine-build = "docker build -t dev-machine /media/diestrin/data/Projects/dev-machine";
    };

    initContent = ''
      # Spaceship prompt segment order (migrated from prior ~/.zshrc)
      SPACESHIP_PROMPT_ORDER=(
        exit_code
        time
        dir
        git
        node
        exec_time
        line_sep
        char
      )

      # Single-user Nix (installer profile) — keep before local bins.
      if [ -e "$HOME/.nix-profile/etc/profile.d/nix.sh" ]; then
        . "$HOME/.nix-profile/etc/profile.d/nix.sh"
      fi

      # nvm stays unmanaged (not a global language runtime in HM).
      export NVM_DIR="$HOME/.nvm"
      [ -s "$NVM_DIR/nvm.sh" ] && . "$NVM_DIR/nvm.sh"
      [ -s "$NVM_DIR/bash_completion" ] && . "$NVM_DIR/bash_completion"

      export PATH="$HOME/.local/bin:$PATH"
    '';
  };

  home.packages = [ pkgs.spaceship-prompt ];
}
