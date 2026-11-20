# 窑炉保温复算台

## 启动

```sh
docker compose up --build
```

打开 `http://localhost:18440`，切换干净样例与脏样例，查看数据判定和来源行。
可以在工作台上传同格式的 UTF-8 JSON。签核后可重跑并下载带输入快照、运行清单与证据的 JSON 凭证。

## 核验

```sh
docker compose exec -T app pytest -q
```

本机也可安装 `requirements.txt` 后执行 `python -m pytest -q`。
SQLite 默认保存在 `instance/ledger.sqlite3`，容器使用 `state` 命名卷。需要重建时，先备份归档，再执行 `docker compose down -v`。

## 模块

炉单采集、热电偶校正、热区对齐、保温计时、断档复判、炉批勾稽、签核归档。
接口索引在 `/docs`，字段和边界见 [数据字典](docs/DATA-DICTIONARY.md)，规则与测试见 [深度登记](docs/DEPTH.md)。

已下载的凭证可用 `python -m app.modules.m7_archive.verify 证据.json` 检查输入、结果和签核摘要。
