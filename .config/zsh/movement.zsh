# completion
autoload -Uz compinit
compinit

zstyle ':completion:*' menu select
zstyle ':completion:*' matcher-list 'm:{a-z}={A-Z}'

# plugins
source /usr/share/zsh/plugins/zsh-autosuggestions/zsh-autosuggestions.zsh
source /usr/share/zsh/plugins/zsh-syntax-highlighting/zsh-syntax-highlighting.zsh

# fzf
[ -f /usr/share/fzf/key-bindings.zsh ] && source /usr/share/fzf/key-bindings.zsh
[ -f /usr/share/fzf/completion.zsh ] && source /usr/share/fzf/completion.zsh

# zoxide
eval "$(zoxide init zsh)"

# qol
setopt autocd
setopt correct
# smart word movement:
# / is a separate token
# spaces are skipped
# -word and --word are one token
# pipa-pupa is pipa + -pupa
WORDCHARS=${WORDCHARS//\/}

__smart_forward_word() {
  emulate -L zsh

  local len=${#BUFFER}
  local i=$CURSOR
  local c j

  while (( i < len )) && [[ ${BUFFER:$i:1} == [[:space:]] ]]; do
    ((i++))
  done

  (( i >= len )) && {
    CURSOR=$len
    return
  }

  c=${BUFFER:$i:1}

  if [[ $c == "/" ]]; then
    ((i++))
  elif [[ $c == "-" ]]; then
    j=$i
    while (( j < len )) && [[ ${BUFFER:$j:1} == "-" ]]; do
      ((j++))
    done

    if (( j < len )) && [[ ${BUFFER:$j:1} == [[:alnum:]_] ]]; then
      i=$j
      while (( i < len )) && [[ ${BUFFER:$i:1} == [[:alnum:]_] ]]; do
        ((i++))
      done
    else
      while (( i < len )) && [[ ${BUFFER:$i:1} == "-" ]]; do
        ((i++))
      done
    fi
  elif [[ $c == [[:alnum:]_] ]]; then
    while (( i < len )) && [[ ${BUFFER:$i:1} == [[:alnum:]_] ]]; do
      ((i++))
    done
  else
    ((i++))
  fi

  CURSOR=$i
}

__smart_backward_word() {
  emulate -L zsh

  local i=$CURSOR
  local c

  while (( i > 0 )) && [[ ${BUFFER:$((i - 1)):1} == [[:space:]] ]]; do
    ((i--))
  done

  (( i <= 0 )) && {
    CURSOR=0
    return
  }

  c=${BUFFER:$((i - 1)):1}

  if [[ $c == "/" ]]; then
    ((i--))
  elif [[ $c == [[:alnum:]_] ]]; then
    while (( i > 0 )) && [[ ${BUFFER:$((i - 1)):1} == [[:alnum:]_] ]]; do
      ((i--))
    done

    while (( i > 0 )) && [[ ${BUFFER:$((i - 1)):1} == "-" ]]; do
      ((i--))
    done
  elif [[ $c == "-" ]]; then
    while (( i > 0 )) && [[ ${BUFFER:$((i - 1)):1} == "-" ]]; do
      ((i--))
    done
  else
    ((i--))
  fi

  CURSOR=$i
}

__smart_backward_kill_word() {
  emulate -L zsh

  local old=$CURSOR
  zle __smart_backward_word
  local new=$CURSOR

  (( new == old )) && return

  CUTBUFFER=${BUFFER:$new:$((old - new))}
  BUFFER="${BUFFER:0:$new}${BUFFER:$old}"
  CURSOR=$new
}

zle -N __smart_forward_word
zle -N __smart_backward_word
zle -N __smart_backward_kill_word
zle -N smart-forward-word __smart_forward_word

ZSH_AUTOSUGGEST_PARTIAL_ACCEPT_WIDGETS+=(smart-forward-word)

# key bindings
bindkey '^[[1;5C' smart-forward-word
bindkey '^[[1;5D' __smart_backward_word
bindkey '^H' __smart_backward_kill_word
bindkey -e
bindkey '^[[3~' delete-char
bindkey '^?' backward-delete-char
bindkey '^[[H' beginning-of-line
bindkey '^[[F' end-of-line
bindkey '^[[1~' beginning-of-line
bindkey '^[[4~' end-of-line
bindkey '^[[5~' up-line-or-history
bindkey '^[[6~' down-line-or-history
