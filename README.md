<p align="center">
  <img src="packaging/linux/io.github.sugarycandybar.Hosty.svg" alt="Hosty icon" width="128" />
</p>

<h1 align="center">Better-Hosty ⚡ (Vibe Coded Edition)</h1>

<p align="center">
  <b>Gerenciador Moderno e Nativo de Servidores de Minecraft para Linux e Windows</b>
  <br><br>
  <a href="https://github.com/Fepaab/Better-Hosty"><img src="https://img.shields.io/badge/Vibe%20Coded-100%25%20AI%20Powered-purple?style=for-the-badge&logo=google"></a>
  <a href="LICENSE"><img src="https://img.shields.io/github/license/sugarycandybar/Hosty?style=for-the-badge&label=License&color=blue"></a>
  <a href="https://python.org"><img src="https://img.shields.io/badge/Python-GTK4%20%7C%20Libadwaita-blue?style=for-the-badge&logo=python"></a>
</p>

> 🚀 **Vibe Coded Project**: Esta versão do Hosty foi completamente reformulada, expandida e **Vibe Codada com Inteligência Artificial** (Google DeepMind Antigravity AI). Todo o código de suporte multi-modloader, integrações de APIs e correções de interface foram desenvolvidos em sintonia via prompt & pair programming!

---

## ✨ O que há de novo na Vibe Coded Edition?

- 🛠️ **Suporte Multi-Software Completo**:
  - **Fabric** & **Quilt** (Suporte total a mods e modpacks).
  - **Paper** & **Purpur** (Servidores de alta performance com gerenciamento de Plugins via PaperMC API v3).
  - **Forge** & **NeoForge** (Instalação e inicialização nativa via instaladores oficiais e execução via `unix_args.txt`).
  - **Vanilla** (Servidores originais com suporte dedicado a DataPacks).
- 🧩 **Integração Modrinth Inteligente**:
  - Filtro dinâmico por software: **Mods** para Fabric/Quilt/Forge/NeoForge, **Plugins** para Paper/Purpur e **DataPacks** para Vanilla.
  - Resolução automática de dependências rigorosamente alinhadas com o modloader e a versão exata do Minecraft.
- 🧹 **Interface Limpa & Otimizada**:
  - Remoção completa de dependências desnecessárias (como Playit.gg).
  - Nomes de softwares simplificados e elegantes no diálogo de criação.
  - Ajuste dinâmico das pastas de destino (`plugins/`, `mods/`, `world/datapacks/`).

---

## 🎮 Funcionalidades Principais

- ⚡ **Instalação em 1-Clique**: Baixa automaticamente os executáveis, loaders e dependências do Java quando necessário.
- 🖥️ **Console Interativo em Tempo Real**: Envie comandos e acompanhe logs ao vivo.
- 📊 **Monitoramento de Desempenho**: Gráficos ao vivo de consumo de CPU e Memória RAM.
- 📂 **Gerenciador de Arquivos & Mundos**: Explore mundos, dimensões, backups e instaladores diretamente no aplicativo.
- 👥 **Controle de Jogadores**: Gerencie Whitelist e lista de banidos facilmente.

---

## 🏃 Como Rodar

### Linux (GTK4 / Libadwaita)

1. Instale as dependências do sistema GTK4/Libadwaita e PyGObject da sua distribuição.
2. Instale as dependências Python:

```bash
python3 -m pip install requests psutil Pillow
```

3. Execute o aplicativo:

```bash
python3 hosty.py
```

### Windows (MSYS2 UCRT64)

Recomendado ambiente MSYS2 UCRT64:

```bash
pacman -Suy
pacman -S mingw-w64-ucrt-x86_64-python mingw-w64-ucrt-x86_64-python-gobject mingw-w64-ucrt-x86_64-python-requests mingw-w64-ucrt-x86_64-python-psutil mingw-w64-ucrt-x86_64-python-pillow mingw-w64-ucrt-x86_64-gtk4 mingw-w64-ucrt-x86_64-libadwaita
```

Em seguida, execute no shell UCRT64:

```bash
python hosty.py
```

---

## 🖼️ Capturas de Tela

<p align="center">
	<img src="packaging/linux/screenshots/console.png" alt="Console view" width="900" />
</p>

- **Console**: Stream de logs em tempo real e envio de comandos.

<p align="center">
	<img src="packaging/linux/screenshots/performance.png" alt="Performance view" width="900" />
</p>

- **Performance**: Monitoramento ao vivo do consumo de hardware.

<p align="center">
	<img src="packaging/linux/screenshots/files.png" alt="Files and worlds view" width="900" />
</p>

- **Arquivos & Mods**: Integração com Modrinth para mods, plugins e datapacks com resolução de dependências.

---

<p align="center">
  <i>Better-Hosty - Powered by Vibe Coding ⚡</i>
</p>
