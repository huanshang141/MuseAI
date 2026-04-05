#!/bin/bash
# scripts/setup-worktree-env.sh

set -e

WORKTREE_ROOT=$(git rev-parse --show-toplevel)
MAIN_REPO_ROOT=$(git worktree list | head -1 | awk '{print $1}')
BACKEND_DIR="backend"

echo "Setting up worktree environment..."

if [ -f "$MAIN_REPO_ROOT/$BACKEND_DIR/.env" ]; then
    echo "Creating symlink to main repo .env..."
    
    if [ -f "$WORKTREE_ROOT/$BACKEND_DIR/.env" ]; then
        echo "Backing up existing .env to .env.backup"
        mv "$WORKTREE_ROOT/$BACKEND_DIR/.env" "$WORKTREE_ROOT/$BACKEND_DIR/.env.backup"
    fi
    
    ln -s "$MAIN_REPO_ROOT/$BACKEND_DIR/.env" "$WORKTREE_ROOT/$BACKEND_DIR/.env"
    echo "✓ Symlink created: $WORKTREE_ROOT/$BACKEND_DIR/.env -> $MAIN_REPO_ROOT/$BACKEND_DIR/.env"
else
    echo "⚠ No .env found in main repo. Creating from .env.example..."
    cp "$WORKTREE_ROOT/$BACKEND_DIR/.env.example" "$WORKTREE_ROOT/$BACKEND_DIR/.env"
    echo "✓ Created .env from template. Please fill in your credentials."
fi

if [ -f "$MAIN_REPO_ROOT/$BACKEND_DIR/.env.test" ]; then
    if [ ! -L "$WORKTREE_ROOT/$BACKEND_DIR/.env.test" ]; then
        ln -sf "$MAIN_REPO_ROOT/$BACKEND_DIR/.env.test" "$WORKTREE_ROOT/$BACKEND_DIR/.env.test"
        echo "✓ Symlink created for .env.test"
    fi
fi

echo "Environment setup complete!"
