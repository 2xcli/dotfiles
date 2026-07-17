# Load custom zsh config files
for file in "$HOME"/.config/zsh/*.zsh; do
  [ -r "$file" ] && source "$file"
done
