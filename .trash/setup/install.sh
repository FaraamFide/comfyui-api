#!/bin/bash
set -e # Выход при любой ошибке.

# --- Цвета для красивого вывода ---
BLUE='\033[1;34m'
GREEN='\033[1;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# --- КОНФИГУРАЦИЯ ПУТЕЙ ---
SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" &> /dev/null && pwd)
PROJECT_DIR=$(dirname "$SCRIPT_DIR")
COMFYUI_DIR="${PROJECT_DIR}/comfyui"
VENV_DIR="${PROJECT_DIR}/venv"
CUSTOM_NODES_DIR="${COMFYUI_DIR}/custom_nodes"

# --- ШАГ 0: ПРОВЕРКА ТОКЕНА HUGGING FACE ---
clear
echo -e "${BLUE}--- Проверка конфигурации аутентификации ---${NC}"
if [ -z "$HF_TOKEN" ]; then
    echo -e "${RED}Ошибка: Переменная окружения HF_TOKEN не установлена.${NC}"
    echo -e "${YELLOW}export HF_TOKEN='hf_ВАШ_ТОКЕН_HUGGING_FACE'${NC}"
    exit 1
fi
echo -e "  > ${GREEN}Токен Hugging Face (HF_TOKEN) найден.${NC}"

# --- ИНТЕРАКТИВНЫЕ НАСТРОЙКИ ---
echo -e "\n${BLUE}--- Настройка параметров установки ---${NC}"
echo -e "Выберите уровень детализации логов:"
select log_level in "Тихий (рекомендуется)" "Подробный (для отладки)"; do
    case $log_level in
        "Тихий (рекомендуется)") GIT_QUIET="--quiet"; PIP_QUIET="--log /dev/null --quiet"; APT_QUIET="-qq"; break ;;
        "Подробный (для отладки)") GIT_QUIET=""; PIP_QUIET=""; APT_QUIET=""; break ;;
    esac
done
echo -e "\nВыберите режим скачивания моделей:"
select model_mode in "Скачать всё (по умолчанию)" "Ручной выбор"; do
    case $model_mode in
        "Скачать всё (по умолчанию)") MANUAL_SELECT=false; break;;
        "Ручной выбор") MANUAL_SELECT=true; break;;
    esac
done

# --- ЗАПУСК УСТАНОВКИ ---
clear
echo -e "${BLUE}--- Запуск полного сетапа (v5.2 - hf_hub) ---${NC}"
echo "Корневая директория проекта: ${PROJECT_DIR}"
echo "--------------------------------------------------------"

# --- ШАГ 1: Установка системных зависимостей ---
echo -e "${BLUE}[1/5] Проверка и установка системных зависимостей...${NC}"
sudo -v
sudo apt-get update ${APT_QUIET}
sudo apt-get install -y ${APT_QUIET} python3.11 python3.11-venv
echo -e "  > ${GREEN}Системные зависимости в порядке.${NC}"

# --- ШАГ 2: Клонирование репозитория ComfyUI ---
echo -e "${BLUE}[2/5] Проверка репозитория ComfyUI...${NC}"
if [ ! -d "$COMFYUI_DIR" ]; then
    echo "  > Клонирование ComfyUI..."
    git clone --depth 1 ${GIT_QUIET} "https://github.com/comfyanonymous/ComfyUI.git" "$COMFYUI_DIR"
else
    echo "  > Директория ComfyUI уже существует."
fi

# --- ШАГ 3: Настройка виртуального окружения Python ---
echo -e "${BLUE}[3/5] Настройка виртуального окружения Python 3.11...${NC}"
if [ ! -d "$VENV_DIR" ]; then
    echo "  > Создание виртуального окружения..."
    python3.11 -m venv "$VENV_DIR"
fi
source "$VENV_DIR/bin/activate"
echo "  > Виртуальное окружение активировано."
pip install --upgrade pip ${PIP_QUIET}
echo -e "  > ${GREEN}pip успешно обновлен.${NC}"

# --- ШАГ 4.0: Установка зависимостей ComfyUI ---
echo -e "${BLUE}[4.0/5] Установка зависимостей ComfyUI...${NC}"
sed -i 's/^torch\(==.*\)\?$/torch==2.7.0/' comfyui/requirements.txt # установка строго 2.7.0 чтобы установить xformers
pip install ${PIP_QUIET} --no-cache-dir -r "${COMFYUI_DIR}/requirements.txt"
echo -e "  > ${GREEN}Зависимости ComfyUI установлены.${NC}"

# --- ШАГ 4.1: Установка Python-зависимостей ---
echo -e "${BLUE}[4.1/5] Установка скрипт и performance-библиотек Python...${NC}"
pip install ${PIP_QUIET} --no-cache-dir -r "${SCRIPT_DIR}/requirements.txt"
echo -e "  > ${GREEN}Основные зависимости установлены.${NC}"


# --- ШАГ 5: Установка кастомных нод и их зависимостей ---
echo -e "${BLUE}[5/5] Установка кастомных нод и их зависимостей...${NC}"
while IFS= read -r line || [[ -n "$line" ]]; do
    shopt -s extglob; line_trimmed="${line##*( )}"; shopt -u extglob
    if [[ -z "$line_trimmed" || "$line_trimmed" == \#* ]]; then continue; fi
    repo_url=$line_trimmed
    repo_name=$(basename "$repo_url" .git)
    target_dir="${CUSTOM_NODES_DIR}/${repo_name}"
    if [ ! -d "$target_dir" ]; then
        echo -e "  ${CYAN}> Клонирование ${repo_name}...${NC}"
        git clone --depth 1 ${GIT_QUIET} "${repo_url}" "$target_dir"
    fi
done < "${SCRIPT_DIR}/custom_nodes.txt"
for node_dir in ${CUSTOM_NODES_DIR}/*/; do
    if [ -f "${node_dir}requirements.txt" ]; then
        echo -e "  ${CYAN}> Установка зависимостей для $(basename "$node_dir")...${NC}"
        pip install ${PIP_QUIET} -r "${node_dir}requirements.txt"
    fi
done
echo -e "  > ${GREEN}Все активные кастомные ноды и их зависимости установлены.${NC}"

# --- ШАГ 6: Скачивание моделей ---
echo -e "${BLUE}[6/6] Скачивание моделей...${NC}"
python3 "${SCRIPT_DIR}/download_models.py" --links-file "${SCRIPT_DIR}/model_links.txt" $([ "$MANUAL_SELECT" = true ] && echo "--manual") --token "$HF_TOKEN"


# --- ФИНАЛЬНЫЕ ИНСТРУКЦИИ ---
echo ""
echo -e "${GREEN}=======================================================${NC}"
echo -e "${GREEN}    УСТАНОВКА ПОЛНОСТЬЮ И УСПЕШНО ЗАВЕРШЕНА!         ${NC}"
echo -e "${GREEN}=======================================================${NC}"
echo ""
echo "Следующий шаг:"
echo "  1. Активируйте виртуальное окружение, если еще не активно:"
echo -e "     ${YELLOW}source ${PROJECT_DIR}/venv/bin/activate${NC}"
echo "  2. Запустите ComfyUI для создания воркфлоу:"
echo -e "     ${YELLOW}python ${COMFYUI_DIR}/main.py --pytorch-deterministic${NC}"
echo ""