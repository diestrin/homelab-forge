{
  description = "homelab-forge L0 project template (flake + direnv)";

  inputs.nixpkgs.url = "github:NixOS/nixpkgs/nixos-25.05";

  outputs =
    { nixpkgs, ... }:
    let
      system = "x86_64-linux";
      pkgs = nixpkgs.legacyPackages.${system};
    in
    {
      devShells.${system}.default = pkgs.mkShell {
        # Generic tools only — add language runtimes per project.
        packages = with pkgs; [
          git
          jq
          ripgrep
        ];
      };
    };
}
