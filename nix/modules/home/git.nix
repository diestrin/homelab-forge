{
  programs.git = {
    enable = true;
    userName = "Diego Barahona";
    userEmail = "diestrin@gmail.com";
    extraConfig = {
      init.defaultBranch = "main";
      pull.rebase = false;
    };
  };
}
