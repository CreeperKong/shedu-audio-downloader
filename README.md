# 上海中小学教材配套音视频资料下载工具
## 依赖安装
```
pip install requests beautifulsoup4 colorama tqdm
```
## 使用方法
```
usage: 上海中小学教材配套音频下载工具.py [-h] -c CODES [-d] [-t TARGET] [-f {ct,c,t,tc,n}] [-v | -s]

命令行选项:
  -h, --help            显示帮助
  -c, --codes CODES     附上8位数提取码，如需多个请使用半角逗号分隔
  -d, --download        添加此选项以下载文件
  -t, --target TARGET   指定目标目录（默认为当前工作目录）
  -f, --folder-format {ct,c,t,tc,n}
                        用文件夹分类
                        'ct': {提取码}-{标题}
                        'c': {提取码}
                        't': {标题}
                        'tc': {标题}-{提取码}
                        'n': 不进行分类（默认）
  -v, --verbose         显示进度（默认）
  -s, --silent          不显示进度
```
