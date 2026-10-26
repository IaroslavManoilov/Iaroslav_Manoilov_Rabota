# Проверка переносимого пакета

Проверено локально 2026-10-26 на Windows, без изменения CMS:

- Python compilation: cms_read.py и verify_images.py; CLI help reader.
- Shell syntax: оба macOS shell-скрипта через bash -n.
- Семь offline JavaScript contract tests: health без token в результате, запрет fuzzy SKU, пагинация и hidden variant с полной семьёй, duplicate SKU, незавершённая пагинация, auth failure, несогласованные связи parent.
- Фото-проверка: отсутствующие файлы отклонены, четыре PNG 750×750 приняты структурно, неверный размер отклонён. Даже структурно корректная серия не маркируется completed без визуального контроля.

Воспроизведение offline JS-проверок при установленном Node.js:

```sh
node --test tests/cms-read.test.mjs
```

Node.js нужен только для этих developer tests; Python reader не требует Node.js. Проверки не подтверждают текущую схему сервера ViTRA, права нового аккаунта, macOS launch, Content project, create/update API и media-preservation. Эти проверки остаются первому рабочему сеансу на Mac. Никаких live-операций с карточками при сборке пакета не выполняли.
