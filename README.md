# Pokébot — Discord-бот для покемон-ролевой игры

Слэш-команды, MongoDB (motor), PokéAPI (aiohttp). Требуется **Python 3.10+**.

## Структура

```
pokebot/
├── bot.py             # точка входа, загрузка cog'ов, синхронизация команд
├── database.py        # MongoDB: get_trainer, update_trainer
├── pokeapi_client.py  # запросы к PokéAPI + кэш
├── utils.py           # форматирование эмбедов
├── cogs/
│   ├── profile.py     # /profile, /balance
│   ├── team.py        # /party, /pc, /team_add, /team_remove, /setnick
│   ├── inventory.py   # /inventory, /shop
│   └── pokedex.py     # /pokedex, /catch
├── requirements.txt
└── .env.example       # скопируйте в .env
```

## 1. Создание бота в Discord

1. Откройте https://discord.com/developers/applications → **New Application**, введите имя.
2. Вкладка **Bot** → **Reset Token** → скопируйте токен (он показывается один раз). Никому его не показывайте.
3. Там же, в разделе **Privileged Gateway Intents**, можно включить **Message Content Intent**. Этому боту он *не обязателен* (слэш-команды работают без него), но включение ничему не мешает и пригодится, если позже добавите текстовые команды.
4. Вкладка **OAuth2 → URL Generator**: отметьте scopes `bot` и `applications.commands`; в правах — `Send Messages`, `Embed Links`, `Use Slash Commands`.
5. Откройте сгенерированную ссылку, выберите сервер и подтвердите приглашение.

## 2. MongoDB

**Локально**
- Windows/macOS/Linux: установите MongoDB Community Server (https://www.mongodb.com/try/download/community) и запустите службу `mongod`.
- Или через Docker: `docker run -d --name mongo -p 27017:27017 mongo:7`
- Строка подключения: `mongodb://localhost:27017`

**Облако Atlas (бесплатно)**
1. Зарегистрируйтесь на https://www.mongodb.com/atlas, создайте бесплатный кластер (M0).
2. **Database Access** → создайте пользователя с паролем.
3. **Network Access** → добавьте ваш IP (для теста можно `0.0.0.0/0`).
4. **Connect → Drivers** → скопируйте строку вида  
   `mongodb+srv://USER:PASSWORD@cluster0.xxxxx.mongodb.net/?retryWrites=true&w=majority`  
   и подставьте свой пароль (спецсимволы в пароле кодируются, например `@` → `%40`).

## 3. Установка и запуск

```bash
cd pokebot
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env            # Windows: copy .env.example .env
# впишите DISCORD_TOKEN и MONGODB_URI в .env
python bot.py
```

В `.env` можно указать `GUILD_ID` (ID вашего сервера): тогда команды появятся сразу.
Без него глобальная синхронизация может занять до часа.

## 4. Команды

| Команда | Пример |
|---|---|
| `/profile` | профиль тренера |
| `/balance` | баланс Pokébucks |
| `/party` | команда (до 6) |
| `/pc` | ПК, по 10 на страницу, кнопки ◀ ▶ |
| `/inventory` | инвентарь |
| `/shop item:Покебол quantity:5` | купить 5 покеболов |
| `/pokedex` | первые 15 известных видов |
| `/catch` | поймать случайного покемона (−1 покебол) |
| `/team_add instance_id:a1b2c3d4` | ПК → команда |
| `/team_remove instance_id:a1b2c3d4` | команда → ПК |
| `/setnick instance_id:a1b2c3d4 nickname:Искра` | кличка (`-` — сбросить) |

Для ID в командах работает автодополнение. Новичок получает 500 Pokébucks, 5 покеболов и 3 зелья.
Пойманные покемоны попадают в ПК.

## 5. Частые ошибки

| Проблема | Решение |
|---|---|
| Команды не появляются | Укажите `GUILD_ID` в `.env`; проверьте, что при приглашении был scope `applications.commands`; глобальная синхронизация идёт до часа |
| `LoginFailure: Improper token` | Токен неверный или сброшен — сгенерируйте новый и обновите `.env` |
| `ServerSelectionTimeoutError` | MongoDB не запущена / неверная строка / IP не добавлен в Network Access Atlas |
| `Authentication failed` | Неверный логин/пароль; закодируйте спецсимволы пароля |
| `The DNS query name does not exist` (Atlas) | Установите `dnspython` (`pip install -r requirements.txt`), проверьте формат `mongodb+srv://` |
| `Missing Access` / `Missing Permissions` | У бота нет прав в канале (Send Messages, Embed Links) |
| `The application did not respond` | Команда выполнялась дольше 3 секунд — обычно временные проблемы PokéAPI, повторите |
| `PokéAPI недоступен` | Проблемы сети или лимиты API; данные кэшируются, повторный запрос быстрее |
| `ModuleNotFoundError` | Активируйте venv и выполните `pip install -r requirements.txt` |

## 6. Как расширять

**Опыт и уровни.** Добавьте покемону поле `xp`. Кривая, например: `xp_to_next = level ** 3`.
После боя: `$inc: {"party.$.xp": gained}` и функция `check_level_up`, которая повышает `level`, пока хватает опыта.
Опыт за победу: `base_exp * enemy_level / 7`.

**Боевая система.** Новый `cogs/battle.py`: команда `/battle @user`, состояние боя хранится в памяти
(`dict[channel_id, Battle]`) или в коллекции `battles`. Ход выбирается кнопками (`discord.ui.View`) —
атаки из `moves`. Урон: `((2*L/5+2) * Power * A/D / 50 + 2) * STAB * type_multiplier * random(0.85..1)`.
Мощность атак берите из `https://pokeapi.co/api/v2/move/{name}`, множители типов — из `/type/{name}`
(`damage_relations`). Победитель: `$inc wins`, проигравший: `$inc losses`, награда: `$inc pokebucks`.

**Эволюции.** Из `/pokemon-species/{id}` берите `evolution_chain.url`, затем данные цепочки
(`chain.evolves_to[].evolution_details.min_level`). Когда уровень достиг порога — меняйте `species_id`
через `$set: {"party.$.species_id": new_id}` и добавляйте новый вид в `pokedex_known`.
Эволюции по камням реализуйте через предметы из `/shop`.

**Прочее.** Использование зелий (`/use`), шанс поимки, зависящий от типа покебола, обмен между игроками,
ежедневная награда, сохранение кэша PokéAPI на диск или в Mongo, отдельные коллекции при росте данных
(ограничение документа — 16 МБ).
