AudioFlow Studio macOS 打包说明

1. 把 client_v31 整个文件夹复制到 Mac。
2. 安装 Homebrew 后执行：
   brew install python ffmpeg sox
3. 在 client_v31 目录执行：
   chmod +x build_mac_app.sh
   ./build_mac_app.sh
4. 成功后会生成：
   AudioFlow_Studio_Mac.zip
5. 把这个 zip 放到公网后台：
   data/updates/AudioFlow_Studio_Mac.zip
6. version.txt 写客户端版本号，例如：
   3.5.4

说明：
- Windows 更新包仍然使用 data/updates/AudioFlow_Studio_v31.exe。
- Mac 更新包使用 data/updates/AudioFlow_Studio_Mac.zip。
- 后台会根据客户端 platform=windows 或 platform=macos 自动返回对应更新包。
- 不要删除 data/licenses.db，卡密数据都在里面。
