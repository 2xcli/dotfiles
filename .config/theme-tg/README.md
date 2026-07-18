[Назад к README.md](../../README.md)

# Telegram theme from Matugen

Автоматически собирает тему Telegram Desktop из акцентного цвета Matugen и
публикует её в Telegram. При быстрой смене обоев отправляет только последний
устойчивый цвет.

## Что происходит при смене обоев

Matugen записывает новый `accent_color` в конфиг Luminous и вызывает
`tg-theme-request`. Команда сразу возвращает управление Matugen, а фоновый
воркер ждёт 1.5 секунды без новых смен обоев. Затем он собирает архив темы и
обновляет её в Telegram. Если обои успели поменяться во время загрузки, воркер
повторяет цикл для нового цвета.

Задержка задаётся в `config.local.toml`:

```toml
[theme]
debounce_seconds = 1.5
```

## Файлы в Git

В репозиторий можно добавлять:

```text
theme.py
tg-theme-request
base.tdesktop-theme
requirements.txt
config.example.toml
README.md
.gitignore
```

Никогда не добавляй:

```text
config.local.toml   # api_hash, slug, личные настройки
*.session           # авторизация Telegram
.venv/              # локальное виртуальное окружение Python
```

`.gitignore` уже исключает эти файлы.

## Размещение в dotfiles

Храни проект в `~/.config/tg-theme`. В репозитории dotfiles это обычно выглядит
так:

```text
dotfiles/
  dotfiles/
    .config/tg-theme/
      ...файлы этого проекта...
    .local/bin/
      tg-theme-request -> ../../.config/tg-theme/tg-theme-request
```

После развёртывания dotfiles создай или обнови симлинк:

```sh
ln -sfn ~/.config/tg-theme/tg-theme-request ~/.local/bin/tg-theme-request
```

## Первая настройка

```sh
cd ~/.config/tg-theme
python -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
cp config.example.toml config.local.toml
```

Открой `config.local.toml` и укажи свои `api_id`, `api_hash`, `slug` и название
темы. Каждый пользователь создаёт свои API-данные в [Telegram API Development
Tools](https://my.telegram.org/apps); чужие ключи использовать не нужно.

Затем один раз авторизуй скрипт через QR:

```sh
.venv/bin/python theme.py login
```

Сессия сохранится в `~/.local/state/tg-theme/theme_owner.session`. Это локальная
авторизация Telegram, благодаря которой QR не нужен при каждой смене обоев.

Если переносишь существующую сессию, перемести её туда же:

```sh
mkdir -p ~/.local/state/tg-theme
mv ~/.config/tg-theme/theme_owner.session ~/.local/state/tg-theme/theme_owner.session
```

## Matugen hook

В `~/.config/matugen/config.toml` для шаблона Luminous нужна строка:

```toml
post_hook = 'sh -lc "systemctl --user restart xdg-desktop-portal-luminous.service xdg-desktop-portal.service; ~/.local/bin/tg-theme-request"'
```

Не добавляй в неё `&` или `flock`: их заменяет воркер внутри `theme.py`.

## Команды

```sh
# Собрать тему из текущего акцента, без публикации.
.venv/bin/python theme.py build

# Собрать и сразу опубликовать тему.
.venv/bin/python theme.py sync

# Запросить обычное отложенное обновление, как из Matugen.
.venv/bin/python theme.py request

# Проверить сборку без Matugen и Telegram.
.venv/bin/python theme.py build --accent '#37a6ff' --output /tmp/test.tdesktop-theme
```

## Если ничего не меняется

```sh
ls -l ~/.local/bin/tg-theme-request
tail -f ~/.cache/tg-theme/worker.log
```

В логе должна появиться строка вида `updated: #... → #...`. Если Telegram-сессия
была отозвана, снова выполни `.venv/bin/python theme.py login`.

[Назад к README.md](../../README.md)
