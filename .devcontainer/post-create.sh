#!/bin/bash
set -e

echo "Setting up development environment..."

# Setup ZSH plugins
echo "Setting up ZSH plugins..."
git clone https://github.com/zsh-users/zsh-autosuggestions ${ZSH_CUSTOM:-~/.oh-my-zsh/custom}/plugins/zsh-autosuggestions
git clone https://github.com/zsh-users/zsh-completions ${ZSH_CUSTOM:-${ZSH:-~/.oh-my-zsh}/custom}/plugins/zsh-completions
git clone https://github.com/zsh-users/zsh-history-substring-search ${ZSH_CUSTOM:-~/.oh-my-zsh/custom}/plugins/zsh-history-substring-search
git clone https://github.com/zsh-users/zsh-syntax-highlighting.git ${ZSH_CUSTOM:-~/.oh-my-zsh/custom}/plugins/zsh-syntax-highlighting
git clone https://github.com/matthiasha/zsh-uv-env ${ZSH_CUSTOM:-~/.oh-my-zsh/custom}/plugins/zsh-uv-env
# Setup dotfiles
echo "Setting up dotfiles..."
git clone https://github.com/Baalakay/.dotfiles.git ~/.dotfiles
cd ~/.dotfiles
stow --adopt .
git reset --hard
cd $LOCAL_WORKSPACE_FOLDER

# Ensure .zshrc exists
touch ~/.zshrc

# Replace or add alias cat=batcat
if grep -q '^alias cat=' ~/.zshrc; then
  sed -i 's|^alias cat=.*|alias cat=batcat|' ~/.zshrc
else
  echo 'alias cat=batcat' >> ~/.zshrc
fi

# Add alias bat=batcat if not present
if ! grep -q '^alias bat=batcat' ~/.zshrc; then
  echo 'alias bat=batcat' >> ~/.zshrc
fi

# Install frontend dependencies
if [ -d "/frontend" ]; then
    # Folder exists, run your command
    echo "frontend folder exists, running npom install..."
    cd frontend
    npm install
    cd ..
fi

echo "Development environment setup complete! Launch a new terminal session to begin in your devcontainer."

