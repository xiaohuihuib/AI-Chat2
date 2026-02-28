#!/usr/bin/env python3
"""
AI-Chat2 - 智能对话聊天程序
版本: 2.0.1
功能: 基于pywebview和Flask的单文件可执行聊天应用
"""
import os
import json
import threading
import time
import sys
from pathlib import Path
from typing import Dict, Any, Literal, TypedDict

# 打印Python路径
print(f"Python路径: {sys.path}")
print(f"当前目录: {os.getcwd()}")

# 导入必要的库
from flask import Flask, request, jsonify
import webview
from openai import OpenAI
from openai import OpenAIError, RateLimitError, AuthenticationError

# 应用配置
APP_VERSION = "2.0.1"
APP_NAME = "AI-Chat2"

# 数据目录设置
def get_app_data_dir() -> Path:
    """获取应用数据目录"""
    appdata_dir = os.environ.get('APPDATA')
    if not appdata_dir:
        appdata_dir = Path.home() / 'Documents'
    return Path(appdata_dir) / 'AI_Chat2'

# 创建数据目录
APP_DATA_DIR = get_app_data_dir()
print(f"数据目录: {APP_DATA_DIR}")
APP_DATA_DIR.mkdir(parents=True, exist_ok=True)
print(f"数据目录创建成功: {APP_DATA_DIR.exists()}")

# 配置文件路径
CONFIG_FILE = APP_DATA_DIR / 'config.json'
CHAT_HISTORY_FILE = APP_DATA_DIR / 'chat_history.json'

# 默认配置
DEFAULT_CONFIG = {
    "api_key": "",
    "base_url": "",
    "model": "deepseek-ai/DeepSeek-R1-0528-Qwen3-8B",
    "system_prompt": "你是一个智能助手，帮助用户解决问题。"
}

# 全局变量
app = Flask(__name__)
app.config['SECRET_KEY'] = 'supersecretkey'

#在程序初始化完成后导入TTHSD接口
from TTHSD_interface import TTHSDownloader

# 版本检查URL
VERSION_URL = "https://raw.githubusercontent.com/xiaohuihuib/AI-Chat2/refs/heads/main/aichat.txt"

# 下载临时目录
TEMP_DIR = APP_DATA_DIR / 'temp'
TEMP_DIR.mkdir(parents=True, exist_ok=True)

# 对话管理
def load_config() -> Dict[str, Any]:
    """加载配置"""
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            return DEFAULT_CONFIG.copy()
    return DEFAULT_CONFIG.copy()

def save_config(config: Dict[str, Any]) -> None:
    """保存配置"""
    try:
        print(f"保存配置到: {CONFIG_FILE}")
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(config, f, ensure_ascii=False, indent=2)
        print(f"配置保存成功: {CONFIG_FILE.exists()}")
    except OSError as e:
        print(f"保存配置失败: {e}")

def load_conversations() -> Dict[str, Any]:
    """加载对话历史"""
    print(f"加载对话历史从: {CHAT_HISTORY_FILE}")
    print(f"文件存在: {CHAT_HISTORY_FILE.exists()}")
    if CHAT_HISTORY_FILE.exists():
        try:
            print(f"文件大小: {CHAT_HISTORY_FILE.stat().st_size} bytes")
            with open(CHAT_HISTORY_FILE, 'r', encoding='utf-8') as f:
                content = f.read()
                print(f"文件内容: {content[:200]}...")  # 打印前200个字符
                data = json.loads(content)
                print(f"加载的对话数量: {len(data.get('conversations', {}))}")
                return {
                    'conversations': data.get('conversations', {}),
                    'conversation_titles': data.get('conversation_titles', {})
                }
        except json.JSONDecodeError as e:
            print(f"JSON解析错误: {e}")
        except OSError as e:
            print(f"文件读取错误: {e}")
    else:
        print("文件不存在，返回空数据")
    return {
        'conversations': {},
        'conversation_titles': {}
    }

def save_conversations(data: Dict[str, Any]) -> None:
    """保存对话历史"""
    try:
        print(f"保存对话历史到: {CHAT_HISTORY_FILE}")
        print(f"对话数量: {len(data.get('conversations', {}))}")
        with open(CHAT_HISTORY_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"对话历史保存成功: {CHAT_HISTORY_FILE.exists()}")
    except OSError as e:
        print(f"保存对话历史失败: {e}")

# 全局状态
config = load_config()
conversation_data = load_conversations()
conversations = conversation_data['conversations']
conversation_titles = conversation_data['conversation_titles']

# 事件字典类型定义
class Event(TypedDict):
    Type: Literal['start', 'startOne', 'update', 'end', 'endOne', 'msg', 'err']
    Name: str
    ShowName: str
    ID: str

def callback_func(event_dict: Event, msg_dict: dict[str, str | int | float]):
    # 处理不同类型的事件消息
    event_type: Literal['start', 'startOne', 'update', 'end', 'endOne', 'msg', 'err'] = event_dict.get('Type', '')
    event_name: str = event_dict.get('Name', '')  # 事件名称
    event_showname: str = event_dict.get('ShowName', '')  # 事件显示名称
    event_id: str = event_dict.get('ID', '')  # 事件会话/实例ID
    if event_type == 'update':  # 更新类型事件
        total: int = msg_dict.get('Total', 0)  # 待下载总字节数
        downloaded: int = msg_dict.get('Downloaded', 0)  # 已下载字节数

        # 更新进度显示
        # 注意：Speed 字段已在 TTHSD 内核中移除，需自行计算
        if total > 0:
            percent = (downloaded / total) * 100
            print(f"{event_showname}（{event_id}）：{downloaded}/{total} 字节 ({percent:.2f}%)", end='\r', flush=True)

    elif event_type == 'startOne':  # 单个文件开始下载事件
        url: str = msg_dict.get('URL', '')  # 下载URL地址
        task_id: str = event_dict.get('ID', '')  # 任务标识符（从 event 获取）
        index: int = msg_dict.get('Index', 0)  # 任务索引编号
        total_tasks: int = msg_dict.get('Total', 0)  # 总任务数量
        print(f"\n{event_showname}（{event_id}）：开始下载：{url}，这是第 {index} 个下载任务，总共 {total_tasks} 个任务。")

    elif event_type == 'start':  # 整体下载开始事件
        print(f"\n{event_showname}（{event_id}）：开始下载")

    elif event_type == 'endOne':  # 单个文件下载完成事件
        url: str = msg_dict.get('URL', '')  # 下载URL地址
        task_id: str = event_dict.get('ID', '')  # 任务标识符（从 event 获取）
        index: int = msg_dict.get('Index', 0)  # 任务索引编号
        total_tasks: int = msg_dict.get('Total', 0)  # 总任务数量
        print(f"\n{event_showname}（{event_id}）：下载完成：{url}，这是第 {index} 个下载任务，总共 {total_tasks} 个任务。")

    elif event_type == 'end':  # 整体下载结束事件
        print(f"\n{event_showname}（{event_id}）：下载完成或已被取消")

    elif event_type == 'msg':  # 消息类型事件
        text: str = msg_dict.get('Text', '')  # 消息文本内容
        # 检查是否包含错误信息（0.5.0 版本兼容）
        if text and ('错误' in text or 'Error' in text or '失败' in text):
            print(f"\n{event_showname}（{event_id}）：错误: {text}")
        else:
            print(f"\n{event_showname}（{event_id}）：{text}")

    elif event_type == 'err':  # 错误事件
        error: str = msg_dict.get('Error', '')  # 错误消息内容
        print(f"\n{event_showname}（{event_id}）：错误: {error}")

# 检查更新函数
def check_for_updates() -> Dict[str, Any]:
    """检查是否有新版本可用"""
    try:
        # 临时文件路径
        version_file = TEMP_DIR / 'aichat.txt'
        
        # 使用TTHSD下载器下载版本文件
        with TTHSDownloader() as dl:
            # 下载版本文件
            dl.start_download(
                urls=[VERSION_URL],
                save_paths=[str(version_file)],
                thread_count=8,
                chunk_size_mb=1,
                callback=callback_func
            )
            
            # 等待下载完成（简单实现，实际应该使用回调）
            time.sleep(2)
        
        # 读取版本文件
        if not version_file.exists():
            print(f"版本文件不存在: {version_file}")
            # 尝试使用Python标准库下载（忽略SSL证书验证）
            try:
                import urllib.request
                import ssl
                
                # 忽略SSL证书验证（仅用于版本检查）
                context = ssl._create_unverified_context()
                
                # 下载文件
                with urllib.request.urlopen(VERSION_URL, context=context) as response:
                    with open(version_file, 'wb') as f:
                        f.write(response.read())
                
                if not version_file.exists():
                    return {
                        'current_version': APP_VERSION,
                        'latest_version': None,
                        'update_available': False,
                        'error': '无法下载版本文件'
                    }
            except Exception as e:
                print(f"备用下载方法也失败: {e}")
                return {
                    'current_version': APP_VERSION,
                    'latest_version': None,
                    'update_available': False,
                    'error': f'无法下载版本文件: {str(e)}'
                }
        
        with open(version_file, 'r', encoding='utf-8') as f:
            latest_version = f.read().strip()
        
        print(f"当前版本: {APP_VERSION}")
        print(f"最新版本: {latest_version}")
        print(f"版本文件内容: '{latest_version}'")
        print(f"版本文件长度: {len(latest_version)}")
        
        # 比较版本
        current_version = APP_VERSION
        is_update_available = compare_versions(latest_version, current_version)
        
        print(f"是否有更新: {is_update_available}")
        print(f"版本比较结果: compare_versions('{latest_version}', '{current_version}') = {is_update_available}")
        
        return {
            'current_version': current_version,
            'latest_version': latest_version,
            'update_available': is_update_available
        }
    except Exception as e:
        print(f"检查更新失败: {e}")
        # 尝试使用Python标准库下载（忽略SSL证书验证）
        try:
            # 临时文件路径
            version_file = TEMP_DIR / 'aichat.txt'
            
            import urllib.request
            import ssl
            
            # 忽略SSL证书验证（仅用于版本检查）
            context = ssl._create_unverified_context()
            
            # 下载文件
            with urllib.request.urlopen(VERSION_URL, context=context) as response:
                with open(version_file, 'wb') as f:
                    f.write(response.read())
            
            # 读取版本文件
            if not version_file.exists():
                return {
                    'current_version': APP_VERSION,
                    'latest_version': None,
                    'update_available': False,
                    'error': '无法下载版本文件'
                }
            
            with open(version_file, 'r', encoding='utf-8') as f:
                latest_version = f.read().strip()
            
            print(f"当前版本: {APP_VERSION}")
            print(f"最新版本: {latest_version}")
            
            # 比较版本
            current_version = APP_VERSION
            is_update_available = compare_versions(latest_version, current_version)
            
            print(f"是否有更新: {is_update_available}")
            
            return {
                'current_version': current_version,
                'latest_version': latest_version,
                'update_available': is_update_available
            }
        except Exception as e2:
            print(f"备用下载方法也失败: {e2}")
            return {
                'current_version': APP_VERSION,
                'latest_version': None,
                'update_available': False,
                'error': f'检查更新失败: {str(e)}\n备用方法也失败: {str(e2)}'
            }


def compare_versions(version1: str, version2: str) -> bool:
    """比较两个版本号，返回version1是否大于version2"""
    try:
        v1_parts = list(map(int, version1.split('.')))
        v2_parts = list(map(int, version2.split('.')))
        
        # 确保版本号部分长度相同
        max_length = max(len(v1_parts), len(v2_parts))
        v1_parts.extend([0] * (max_length - len(v1_parts)))
        v2_parts.extend([0] * (max_length - len(v2_parts)))
        
        for v1, v2 in zip(v1_parts, v2_parts):
            if v1 > v2:
                return True
            if v1 < v2:
                return False
        return False
    except:
        return False

# 确保默认对话存在
if 'default' not in conversations:
    conversations['default'] = [{"role": "system", "content": config['system_prompt']}]
    conversation_titles['default'] = "新对话 1"
    save_conversations({
        'conversations': conversations,
        'conversation_titles': conversation_titles
    })

# Flask路由
@app.route('/')
def index():
    """默认路由，返回HTML页面"""
    return HTML_CONTENT

@app.route('/api/config', methods=['GET', 'POST'])
def api_config():
    """配置管理API"""
    global config
    if request.method == 'GET':
        return jsonify(config)
    data = request.json
    if data:
        config.update(data)
        save_config(config)
        # 更新所有对话的系统提示词
        for conv_id in conversations:
            if conversations[conv_id]:
                conversations[conv_id][0] = {"role": "system", "content": config['system_prompt']}
        save_conversations({
            'conversations': conversations,
            'conversation_titles': conversation_titles
        })
    return jsonify({"status": "success"})

@app.route('/api/conversations', methods=['GET', 'POST'])
def api_conversations():
    """对话管理API"""
    global conversations, conversation_titles
    if request.method == 'GET':
        return jsonify({
            'conversations': conversations,
            'conversation_titles': conversation_titles
        })
    data = request.json
    if data:
        # 更新全局变量
        conversations = data.get('conversations', {})
        conversation_titles = data.get('conversation_titles', {})
        # 保存到文件
        save_conversations({
            'conversations': conversations,
            'conversation_titles': conversation_titles
        })
        # 重新加载数据以确保一致性
        conversation_data = load_conversations()
        conversations = conversation_data['conversations']
        conversation_titles = conversation_data['conversation_titles']
    return jsonify({"status": "success"})

@app.route('/api/message', methods=['POST'])
def api_message():
    """消息处理API"""
    data = request.json
    if not data:
        return jsonify({"error": "缺少消息数据"})

    conversation_id = data.get('conversation_id')
    message = data.get('message')

    if not conversation_id or not message:
        return jsonify({"error": "缺少对话ID或消息内容"})

    # 检查API配置
    if not config['api_key'] or not config['base_url']:
        return jsonify({"error": "请先配置API密钥和地址"})

    try:
        # 创建OpenAI客户端
        client = OpenAI(
            api_key=config['api_key'],
            base_url=config['base_url']
        )

        # 获取对话历史
        messages = conversations.get(conversation_id, [])
        if not messages:
            messages = [{"role": "system", "content": config['system_prompt']}]
        messages.append({"role": "user", "content": message})

        # 调用API
        response = client.chat.completions.create(
            model=config['model'],
            messages=messages,
            temperature=0.7,
            max_tokens=2000,
            timeout=30
        )

        # 获取回复
        content = response.choices[0].message.content

        # 更新对话历史
        messages.append({"role": "assistant", "content": content})
        conversations[conversation_id] = messages
        save_conversations({
            'conversations': conversations,
            'conversation_titles': conversation_titles
        })

        return jsonify({"content": content})

    except AuthenticationError:
        return jsonify({"error": "API认证失败，请检查API密钥"})
    except RateLimitError:
        return jsonify({"error": "API速率限制，请稍后再试"})
    except OpenAIError as e:
        return jsonify({"error": f"API调用失败: {str(e)}"})
    except (ConnectionError, TimeoutError, ValueError) as e:
        return jsonify({"error": f"发生错误: {str(e)}"})

@app.route('/api/check-update', methods=['GET'])
def api_check_update():
    """检查更新API"""
    result = check_for_updates()
    return jsonify(result)

# 前端HTML内容
HTML_CONTENT = '''<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>AI-Chat2</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <link href="https://cdn.jsdelivr.net/npm/font-awesome@4.7.0/css/font-awesome.min.css" rel="stylesheet">
    <script>
        tailwind.config = {
            theme: {
                extend: {
                    colors: {
                        primary: '#3B82F6',
                        secondary: '#10B981',
                        dark: '#1F2937',
                        light: '#F3F4F6',
                        'user-bubble': '#DCF8C6',
                        'ai-bubble': '#FFFFFF'
                    },
                    fontFamily: {
                        sans: ['Inter', 'system-ui', 'sans-serif'],
                    },
                }
            }
        }
    </script>
    <style type="text/tailwindcss">
        @layer utilities {
            .content-auto {
                content-visibility: auto;
            }
            .scrollbar-hide {
                -ms-overflow-style: none;
                scrollbar-width: none;
            }
            .scrollbar-hide::-webkit-scrollbar {
                display: none;
            }
        }
    </style>
</head>
<body class="bg-gray-100 font-sans">
    <div class="flex h-screen overflow-hidden">
        <!-- 左侧对话列表 -->
        <div class="w-64 bg-white border-r border-gray-200 flex flex-col">
            <!-- 标题和新建对话按钮 -->
            <div class="p-4 border-b border-gray-200">
                <h1 class="text-xl font-bold text-gray-800">AI-Chat2</h1>
                <p class="text-sm text-gray-500">v2.0.1</p>
            </div>
            <div class="p-4">
                <button id="new-conversation" class="w-full bg-primary text-white py-2 px-4 rounded-lg hover:bg-blue-600 transition-colors flex items-center justify-center">
                    <i class="fa fa-plus mr-2"></i> 新建对话
                </button>
            </div>
            
            <!-- 对话列表 -->
            <div class="flex-1 overflow-y-auto scrollbar-hide">
                <div id="conversation-list" class="p-2">
                    <!-- 对话项将通过JavaScript动态添加 -->
                </div>
            </div>
            
            <!-- 底部菜单 -->
            <div class="p-4 border-t border-gray-200">
                <button id="settings-btn" class="w-full text-gray-600 hover:bg-gray-100 py-2 px-4 rounded-lg flex items-center justify-center">
                    <i class="fa fa-cog mr-2"></i> 设置
                </button>
            </div>
        </div>
        
        <!-- 右侧聊天区域 -->
        <div class="flex-1 flex flex-col">
            <!-- 聊天头部 -->
            <div class="bg-white border-b border-gray-200 p-4 flex items-center justify-between">
                <h2 id="conversation-title" class="text-lg font-semibold text-gray-800">新对话</h2>
                <div class="flex space-x-2">
                    <button id="theme-toggle" class="p-2 text-gray-600 hover:bg-gray-100 rounded-full">
                        <i class="fa fa-moon-o"></i>
                    </button>
                    <button id="help-btn" class="p-2 text-gray-600 hover:bg-gray-100 rounded-full">
                        <i class="fa fa-question-circle"></i>
                    </button>
                    <button id="about-btn" class="p-2 text-gray-600 hover:bg-gray-100 rounded-full">
                        <i class="fa fa-info-circle"></i>
                    </button>
                </div>
            </div>
            
            <!-- 聊天内容区域 -->
            <div id="chat-history" class="flex-1 overflow-y-auto p-4 space-y-4">
                <!-- 欢迎消息 -->
                <div class="flex justify-center">
                    <div class="bg-gray-200 rounded-lg p-4 max-w-md text-center">
                        <h3 class="text-lg font-semibold text-gray-800">欢迎使用AI-Chat2</h3>
                        <p class="text-gray-600 mt-2">输入您的问题，按Enter发送</p>
                        <p class="text-sm text-gray-500 mt-4">当前使用模型: <span id="current-model">deepseek-ai/DeepSeek-R1-0528-Qwen3-8B</span></p>
                    </div>
                </div>
            </div>
            
            <!-- 输入区域 -->
            <div class="bg-white border-t border-gray-200 p-4">
                <div class="flex space-x-2">
                    <input 
                        id="message-input" 
                        type="text" 
                        placeholder="输入消息..." 
                        class="flex-1 border border-gray-300 rounded-lg py-2 px-4 focus:outline-none focus:ring-2 focus:ring-primary focus:border-transparent"
                    >
                    <button id="send-btn" class="bg-primary text-white py-2 px-6 rounded-lg hover:bg-blue-600 transition-colors">
                        <i class="fa fa-paper-plane"></i>
                    </button>
                </div>
                <div class="mt-2 text-sm text-gray-500">
                    <span>按Enter发送消息</span>
                </div>
            </div>
        </div>
    </div>
    
    <!-- 设置模态框 -->
    <div id="settings-modal" class="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 hidden">
        <div class="bg-white rounded-lg shadow-xl w-full max-w-md p-6">
            <div class="flex justify-between items-center mb-4">
                <h3 class="text-lg font-semibold text-gray-800">设置</h3>
                <button id="close-settings" class="text-gray-500 hover:text-gray-700">
                    <i class="fa fa-times"></i>
                </button>
            </div>
            
            <div class="space-y-4">
                <!-- API配置 -->
                <div>
                    <h4 class="text-sm font-medium text-gray-700 mb-2">API配置</h4>
                    <div class="space-y-2">
                        <div>
                            <label class="block text-xs text-gray-500 mb-1">API密钥</label>
                            <input id="api-key" type="password" class="w-full border border-gray-300 rounded-lg py-2 px-4 focus:outline-none focus:ring-2 focus:ring-primary focus:border-transparent">
                        </div>
                        <div>
                            <label class="block text-xs text-gray-500 mb-1">API地址</label>
                            <input id="api-base-url" type="text" class="w-full border border-gray-300 rounded-lg py-2 px-4 focus:outline-none focus:ring-2 focus:ring-primary focus:border-transparent" placeholder="https://api.example.com/v1">
                        </div>
                    </div>
                </div>
                
                <!-- 模型选择 -->
                <div>
                    <h4 class="text-sm font-medium text-gray-700 mb-2">模型选择</h4>
                    <select id="model-select" class="w-full border border-gray-300 rounded-lg py-2 px-4 focus:outline-none focus:ring-2 focus:ring-primary focus:border-transparent">
                        <option value="deepseek-ai/DeepSeek-R1-0528-Qwen3-8B">DeepSeek-R1-0528-Qwen3-8B</option>
                        <option value="deepseek-ai/DeepSeek-R1-Distill-Qwen-7B">DeepSeek-R1-Distill-Qwen-7B</option>
                        <option value="THUDM/glm-4-9b-chat">GLM-4-9B-Chat</option>
                        <option value="qwen/qwen-2.5-7b-instruct">Qwen-2.5-7B-Instruct</option>
                        <option value="mistralai/Mistral-7B-Instruct-v0.3">Mistral-7B-Instruct-v0.3</option>
                        <option value="meta-llama/Llama-3-8B-Instruct">Llama-3-8B-Instruct</option>
                    </select>
                    <div class="flex space-x-2 mt-2">
                        <input id="custom-model-input" type="text" placeholder="输入自定义模型名称" class="flex-1 border border-gray-300 rounded-lg py-2 px-4 focus:outline-none focus:ring-2 focus:ring-primary focus:border-transparent">
                        <button id="add-model-btn" class="bg-primary text-white py-2 px-4 rounded-lg hover:bg-blue-600 transition-colors">
                            添加
                        </button>
                    </div>
                </div>
                
                <!-- 系统提示词 -->
                <div>
                    <h4 class="text-sm font-medium text-gray-700 mb-2">系统提示词</h4>
                    <textarea id="system-prompt" class="w-full border border-gray-300 rounded-lg py-2 px-4 focus:outline-none focus:ring-2 focus:ring-primary focus:border-transparent" rows="3" placeholder="输入系统提示词..."></textarea>
                </div>
                
                <!-- 检测更新按钮 -->
                <button id="check-update-btn" class="w-full bg-secondary text-white py-2 px-4 rounded-lg hover:bg-green-600 transition-colors mb-4">
                    <i class="fa fa-refresh mr-2"></i> 检测更新
                </button>
                
                <!-- 更新检查结果 -->
                <div id="update-result" class="p-3 rounded-lg mb-4 hidden">
                    <p id="update-message" class="text-sm"></p>
                </div>
                
                <!-- 保存按钮 -->
                <button id="save-settings" class="w-full bg-primary text-white py-2 px-4 rounded-lg hover:bg-blue-600 transition-colors">
                    保存设置
                </button>
            </div>
        </div>
    </div>
    
    <!-- 加载中模态框 -->
    <div id="loading-modal" class="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 hidden">
        <div class="bg-white rounded-lg shadow-xl p-6 flex flex-col items-center">
            <div class="animate-spin rounded-full h-12 w-12 border-t-2 border-b-2 border-primary mb-4"></div>
            <p class="text-gray-700">处理中...</p>
        </div>
    </div>
    
    <!-- 错误提示模态框 -->
    <div id="error-modal" class="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 hidden">
        <div class="bg-white rounded-lg shadow-xl w-full max-w-md p-6">
            <div class="flex items-center mb-4">
                <div class="bg-red-100 text-red-500 p-2 rounded-full mr-3">
                    <i class="fa fa-exclamation-circle"></i>
                </div>
                <h3 class="text-lg font-semibold text-gray-800">错误</h3>
            </div>
            <p id="error-message" class="text-gray-600 mb-4"></p>
            <button id="close-error" class="w-full bg-gray-200 text-gray-800 py-2 px-4 rounded-lg hover:bg-gray-300 transition-colors">
                确定
            </button>
        </div>
    </div>
    
    <!-- 帮助模态框 -->
    <div id="help-modal" class="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 hidden">
        <div class="bg-white rounded-lg shadow-xl w-full max-w-md p-6">
            <div class="flex justify-between items-center mb-4">
                <h3 class="text-lg font-semibold text-gray-800">帮助</h3>
                <button id="close-help" class="text-gray-500 hover:text-gray-700">
                    <i class="fa fa-times"></i>
                </button>
            </div>
            <div class="space-y-4 text-gray-600">
                <p><strong>基本操作：</strong></p>
                <ul class="list-disc pl-5 space-y-2">
                    <li>在输入框中输入消息，按Enter或点击发送按钮发送</li>
                    <li>点击左侧的"新建对话"按钮创建新的对话</li>
                    <li>点击对话列表中的对话切换到对应对话</li>
                    <li>点击设置按钮配置API密钥和模型</li>
                </ul>
                <p><strong>快捷键：</strong></p>
                <ul class="list-disc pl-5 space-y-2">
                    <li>Enter: 发送消息</li>
                </ul>
                <p><strong>API配置：</strong></p>
                <p>需要设置API密钥和API地址才能使用AI功能。如果没有API接口，可以从啸AI公益服务站获取。</p>
            </div>
            <button id="close-help-btn" class="w-full mt-4 bg-gray-200 text-gray-800 py-2 px-4 rounded-lg hover:bg-gray-300 transition-colors">
                确定
            </button>
        </div>
    </div>
    
    <!-- 关于模态框 -->
    <div id="about-modal" class="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 hidden">
        <div class="bg-white rounded-lg shadow-xl w-full max-w-md p-6">
            <div class="flex justify-between items-center mb-4">
                <h3 class="text-lg font-semibold text-gray-800">关于</h3>
                <button id="close-about" class="text-gray-500 hover:text-gray-700">
                    <i class="fa fa-times"></i>
                </button>
            </div>
            <div class="space-y-4 text-gray-600">
                <div class="flex flex-col items-center">
                    <h2 class="text-2xl font-bold text-primary mb-2">AI-Chat2</h2>
                    <p class="text-sm text-gray-500">版本 2.0.1</p>
                </div>
                <hr class="border-gray-200">
                <p class="text-center">人工智能对话聊天程序</p>
                <p class="text-center text-sm text-gray-500">基于pywebview和Flask构建</p>
                <hr class="border-gray-200">
                <p class="text-sm">© 2026 小辉辉b. 保留所有权利。</p>
                <p class="text-sm"><a href="https://github.com/xiaohuihuib/AI-Chat2" target="_blank" class="text-blue-500 hover:underline">AI-Chat2 项目链接</a></p>
                <p class="text-sm">本程序使用OpenAI API进行智能对话。</p>
                <p class="text-sm">本程序使用了23XRStudio的TTHSD高速下载器作为获取更新相关信息。</p>
                <p class="text-sm"><a href="https://github.com/TTHSDownloader" target="_blank" class="text-blue-500 hover:underline">TTHSD 组织链接</a></p>
                <p class="text-sm">如果没有API接口，可从啸AI公益服务站获取API接口。</p>
            </div>
            <button id="close-about-btn" class="w-full mt-4 bg-gray-200 text-gray-800 py-2 px-4 rounded-lg hover:bg-gray-300 transition-colors">
                确定
            </button>
        </div>
    </div>
    
    <script>
        // 全局变量
        let currentConversationId = 'default';
        let conversations = {};
        let conversationTitles = {};
        let isProcessing = false;
        
        // 初始化
        function init() {
            console.log('开始初始化应用');
            // 加载配置
            loadConfig();
            
            // 初始化对话
            initConversations();
            
            // 更新对话列表
            updateConversationList();
            
            // 绑定事件
            bindEvents();
            
            // 自动检测更新
            console.log('调用checkUpdateOnLoad');
            checkUpdateOnLoad();
        }
        
        // 加载配置
        function loadConfig() {
            fetch('/api/config').then(response => response.json()).then(config => {
                if (config) {
                    document.getElementById('api-key').value = config.api_key || '';
                    document.getElementById('api-base-url').value = config.base_url || '';
                    
                    // 设置模型选择
                    const modelSelect = document.getElementById('model-select');
                    const selectedModel = config.model || 'deepseek-ai/DeepSeek-R1-0528-Qwen3-8B';
                    
                    // 检查模型是否在下拉列表中
                    let modelExists = false;
                    for (let i = 0; i < modelSelect.options.length; i++) {
                        if (modelSelect.options[i].value === selectedModel) {
                            modelExists = true;
                            break;
                        }
                    }
                    
                    // 如果模型不在下拉列表中，添加它
                    if (!modelExists) {
                        const option = document.createElement('option');
                        option.value = selectedModel;
                        option.textContent = selectedModel;
                        modelSelect.appendChild(option);
                    }
                    
                    // 选择模型
                    modelSelect.value = selectedModel;
                    document.getElementById('system-prompt').value = config.system_prompt || '你是一个智能助手，帮助用户解决问题。';
                    document.getElementById('current-model').textContent = selectedModel;
                }
            });
        }
        
        // 初始化对话
        function initConversations() {
            fetch('/api/conversations').then(response => response.json()).then(data => {
                if (data) {
                    console.log('加载对话历史:', data);
                    conversations = data.conversations || {};
                    conversationTitles = data.conversation_titles || {};
                    
                    if (!conversations[currentConversationId]) {
                        createNewConversation();
                    } else {
                        // 加载当前对话的聊天历史
                        loadChatHistory();
                    }
                    
                    updateConversationList();
                    updateConversationTitle();
                } else {
                    createNewConversation();
                }
            }).catch(error => {
                console.error('加载对话历史失败:', error);
            });
        }
        
        // 创建新对话
        function createNewConversation() {
            const newId = 'conv_' + Date.now();
            conversations[newId] = [{ role: 'system', content: document.getElementById('system-prompt').value }];
            conversationTitles[newId] = '新对话 ' + (Object.keys(conversations).length);
            currentConversationId = newId;
            
            updateConversationList();
            updateConversationTitle();
            clearChatHistory();
            saveConversations();
        }
        
        // 更新对话列表
        function updateConversationList() {
            const listContainer = document.getElementById('conversation-list');
            listContainer.innerHTML = '';
            
            for (const [id, title] of Object.entries(conversationTitles)) {
                const conversationItem = document.createElement('div');
                conversationItem.className = `p-2 rounded-lg cursor-pointer mb-1 ${id === currentConversationId ? 'bg-blue-100 text-blue-800' : 'hover:bg-gray-100'}`;
                conversationItem.textContent = title;
                conversationItem.onclick = () => switchConversation(id);
                conversationItem.oncontextmenu = (e) => {
                    e.preventDefault();
                    showConversationMenu(e, id);
                };
                listContainer.appendChild(conversationItem);
            }
        }
        
        // 显示对话菜单
        function showConversationMenu(event, conversationId) {
            // 创建菜单元素
            const menu = document.createElement('div');
            menu.className = 'absolute bg-white shadow-lg rounded-md py-1 z-50';
            menu.style.left = `${event.clientX}px`;
            menu.style.top = `${event.clientY}px`;
            menu.style.minWidth = '120px';
            
            // 添加重命名选项
            const renameOption = document.createElement('div');
            renameOption.className = 'px-4 py-2 hover:bg-gray-100 cursor-pointer';
            renameOption.textContent = '重命名对话';
            renameOption.onclick = () => renameConversation(conversationId);
            menu.appendChild(renameOption);
            
            // 添加删除选项
            const deleteOption = document.createElement('div');
            deleteOption.className = 'px-4 py-2 hover:bg-gray-100 cursor-pointer text-red-600';
            deleteOption.textContent = '删除对话';
            deleteOption.onclick = () => deleteConversation(conversationId);
            menu.appendChild(deleteOption);
            
            // 添加到文档
            document.body.appendChild(menu);
            
            // 点击其他地方关闭菜单
            setTimeout(() => {
                document.addEventListener('click', function closeMenu(e) {
                    if (!menu.contains(e.target)) {
                        menu.remove();
                        document.removeEventListener('click', closeMenu);
                    }
                });
            }, 0);
        }
        
        // 重命名对话
        function renameConversation(conversationId) {
            const newTitle = prompt('请输入新的对话标题:', conversationTitles[conversationId]);
            if (newTitle && newTitle.trim()) {
                conversationTitles[conversationId] = newTitle.trim();
                updateConversationList();
                saveConversations();
            }
        }
        
        // 删除对话
        function deleteConversation(conversationId) {
            if (Object.keys(conversations).length <= 1) {
                alert('不能删除最后一个对话');
                return;
            }
            
            if (confirm('确定要删除这个对话吗？删除后无法恢复。')) {
                if (conversationId === currentConversationId) {
                    // 切换到第一个对话
                    const otherConversationId = Object.keys(conversations).find(id => id !== conversationId);
                    if (otherConversationId) {
                        switchConversation(otherConversationId);
                    }
                }
                
                // 删除对话
                delete conversations[conversationId];
                delete conversationTitles[conversationId];
                updateConversationList();
                saveConversations();
            }
        }
        
        // 切换对话
        function switchConversation(id) {
            currentConversationId = id;
            updateConversationList();
            updateConversationTitle();
            loadChatHistory();
        }
        
        // 更新对话标题
        function updateConversationTitle() {
            const titleElement = document.getElementById('conversation-title');
            titleElement.textContent = conversationTitles[currentConversationId] || '新对话';
        }
        
        // 加载聊天历史
        function loadChatHistory() {
            clearChatHistory();
            
            const messages = conversations[currentConversationId] || [];
            messages.forEach(msg => {
                if (msg.role !== 'system') {
                    addMessageToChat(msg.role, msg.content);
                }
            });
        }
        
        // 清空聊天历史
        function clearChatHistory() {
            const chatHistory = document.getElementById('chat-history');
            chatHistory.innerHTML = '';
        }
        
        // 添加消息到聊天界面
        function addMessageToChat(role, content) {
            const chatHistory = document.getElementById('chat-history');
            const messageDiv = document.createElement('div');
            
            if (role === 'user') {
                messageDiv.className = 'flex justify-end';
                messageDiv.innerHTML = `
                    <div class="bg-user-bubble rounded-lg p-4 max-w-3/4">
                        <p class="text-gray-800">${content}</p>
                    </div>
                `;
            } else {
                messageDiv.className = 'flex justify-start';
                messageDiv.innerHTML = `
                    <div class="bg-ai-bubble rounded-lg p-4 max-w-3/4 border border-gray-200">
                        <p class="text-gray-800">${content}</p>
                    </div>
                `;
            }
            
            chatHistory.appendChild(messageDiv);
            chatHistory.scrollTop = chatHistory.scrollHeight;
        }
        
        // 发送消息
        function sendMessage() {
            const inputElement = document.getElementById('message-input');
            const message = inputElement.value.trim();
            
            if (!message || isProcessing) return;
            
            // 清空输入框
            inputElement.value = '';
            
            // 添加用户消息到聊天界面
            addMessageToChat('user', message);
            
            // 添加用户消息到对话历史
            if (!conversations[currentConversationId]) {
                conversations[currentConversationId] = [{ role: 'system', content: document.getElementById('system-prompt').value }];
            }
            conversations[currentConversationId].push({ role: 'user', content: message });
            
            // 显示加载中
            document.getElementById('loading-modal').classList.remove('hidden');
            isProcessing = true;
            
            // 调用后端API获取回复
            fetch('/api/message', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    conversation_id: currentConversationId,
                    message: message
                })
            }).then(response => response.json()).then(response => {
                // 隐藏加载中
                document.getElementById('loading-modal').classList.add('hidden');
                isProcessing = false;
                
                if (response.error) {
                    showError(response.error);
                } else {
                    // 添加AI回复到聊天界面
                    addMessageToChat('assistant', response.content);
                    
                    // 添加AI回复到对话历史
                    conversations[currentConversationId].push({ role: 'assistant', content: response.content });
                    
                    // 保存对话
                    saveConversations();
                }
            }).catch(error => {
                document.getElementById('loading-modal').classList.add('hidden');
                isProcessing = false;
                showError('发送消息失败: ' + error.message);
            });
        }
        
        // 保存对话
        function saveConversations() {
            console.log('开始保存对话...');
            console.log('对话数量:', Object.keys(conversations).length);
            console.log('当前对话:', currentConversationId);
            console.log('对话内容:', conversations[currentConversationId]);
            
            fetch('/api/conversations', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    conversations: conversations,
                    conversation_titles: conversationTitles
                })
            }).then(response => {
                console.log('保存对话响应状态:', response.status);
                if (!response.ok) {
                    console.error('保存对话失败:', response.status);
                } else {
                    console.log('保存对话成功');
                }
                return response.json();
            }).then(data => {
                console.log('保存对话响应数据:', data);
            }).catch(error => {
                console.error('保存对话时发生错误:', error);
            });
        }
        
        // 保存设置
        function saveSettings() {
            const config = {
                api_key: document.getElementById('api-key').value,
                base_url: document.getElementById('api-base-url').value,
                model: document.getElementById('model-select').value,
                system_prompt: document.getElementById('system-prompt').value
            };
            
            fetch('/api/config', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(config)
            }).then(() => {
                document.getElementById('settings-modal').classList.add('hidden');
                document.getElementById('current-model').textContent = config.model;
                
                // 更新当前对话的系统提示词
                if (conversations[currentConversationId]) {
                    conversations[currentConversationId][0] = { role: 'system', content: config.system_prompt };
                    saveConversations();
                }
            });
        }
        
        // 显示错误
        function showError(message) {
            document.getElementById('error-message').textContent = message;
            document.getElementById('error-modal').classList.remove('hidden');
        }
        
        // 绑定事件
        function bindEvents() {
            // 发送按钮
            document.getElementById('send-btn').addEventListener('click', sendMessage);
            
            // 输入框回车发送
            document.getElementById('message-input').addEventListener('keypress', function(e) {
                if (e.key === 'Enter') {
                    sendMessage();
                }
            });
            
            // 新建对话
            document.getElementById('new-conversation').addEventListener('click', createNewConversation);
            
            // 设置按钮
            document.getElementById('settings-btn').addEventListener('click', function() {
                // 隐藏更新检查结果
                document.getElementById('update-result').classList.add('hidden');
                // 打开设置模态框
                document.getElementById('settings-modal').classList.remove('hidden');
            });
            
            // 关闭设置
            document.getElementById('close-settings').addEventListener('click', function() {
                document.getElementById('settings-modal').classList.add('hidden');
            });
            
            // 保存设置
            document.getElementById('save-settings').addEventListener('click', saveSettings);
            
            // 关闭错误
            document.getElementById('close-error').addEventListener('click', function() {
                document.getElementById('error-modal').classList.add('hidden');
            });
            
            // 主题切换
            document.getElementById('theme-toggle').addEventListener('click', function() {
                document.body.classList.toggle('dark');
                if (document.body.classList.contains('dark')) {
                    document.body.classList.add('bg-gray-900', 'text-white');
                    document.body.classList.remove('bg-gray-100', 'text-gray-800');
                } else {
                    document.body.classList.remove('bg-gray-900', 'text-white');
                    document.body.classList.add('bg-gray-100', 'text-gray-800');
                }
            });
            
            // 添加自定义模型
            document.getElementById('add-model-btn').addEventListener('click', function() {
                const customModelInput = document.getElementById('custom-model-input');
                const modelSelect = document.getElementById('model-select');
                const customModel = customModelInput.value.trim();
                
                if (customModel) {
                    // 检查模型是否已存在
                    let modelExists = false;
                    for (let i = 0; i < modelSelect.options.length; i++) {
                        if (modelSelect.options[i].value === customModel) {
                            modelExists = true;
                            break;
                        }
                    }
                    
                    if (!modelExists) {
                        // 添加新模型选项
                        const option = document.createElement('option');
                        option.value = customModel;
                        option.textContent = customModel;
                        modelSelect.appendChild(option);
                        
                        // 选择新添加的模型
                        modelSelect.value = customModel;
                        
                        // 清空输入框
                        customModelInput.value = '';
                        
                        // 提示用户
                        alert('模型已添加并选择');
                    } else {
                        alert('该模型已存在');
                    }
                } else {
                    alert('请输入模型名称');
                }
            });
            
            // 帮助按钮
            document.getElementById('help-btn').addEventListener('click', function() {
                document.getElementById('help-modal').classList.remove('hidden');
            });
            
            // 关闭帮助
            document.getElementById('close-help').addEventListener('click', function() {
                document.getElementById('help-modal').classList.add('hidden');
            });
            
            document.getElementById('close-help-btn').addEventListener('click', function() {
                document.getElementById('help-modal').classList.add('hidden');
            });
            
            // 关于按钮
            document.getElementById('about-btn').addEventListener('click', function() {
                document.getElementById('about-modal').classList.remove('hidden');
            });
            
            // 关闭关于
            document.getElementById('close-about').addEventListener('click', function() {
                document.getElementById('about-modal').classList.add('hidden');
            });
            
            document.getElementById('close-about-btn').addEventListener('click', function() {
                document.getElementById('about-modal').classList.add('hidden');
            });
            
            // 检测更新按钮
            document.getElementById('check-update-btn').addEventListener('click', checkUpdate);
        }
        
        // 检查更新
        function checkUpdate() {
            // 显示加载中
            document.getElementById('loading-modal').classList.remove('hidden');
            
            fetch('/api/check-update').then(response => response.json()).then(data => {
                // 隐藏加载中
                document.getElementById('loading-modal').classList.add('hidden');
                
                const resultDiv = document.getElementById('update-result');
                const messageDiv = document.getElementById('update-message');
                
                // 显示结果区域
                resultDiv.classList.remove('hidden');
                
                if (data.error) {
                    resultDiv.className = 'p-3 rounded-lg mb-4 bg-red-100 text-red-700';
                    messageDiv.innerHTML = '检查更新失败: ' + data.error;
                } else if (data.update_available) {
                    resultDiv.className = 'p-3 rounded-lg mb-4 bg-yellow-100 text-yellow-700';
                    messageDiv.innerHTML = `发现新版本 ${data.latest_version}<br>当前版本 ${data.current_version}<br>请前往官网下载更新`;
                } else {
                    resultDiv.className = 'p-3 rounded-lg mb-4 bg-green-100 text-green-700';
                    messageDiv.innerHTML = `当前已是最新版本 ${data.current_version}`;
                }
            }).catch(error => {
                // 隐藏加载中
                document.getElementById('loading-modal').classList.add('hidden');
                
                const resultDiv = document.getElementById('update-result');
                const messageDiv = document.getElementById('update-message');
                
                // 显示结果区域
                resultDiv.classList.remove('hidden');
                resultDiv.className = 'p-3 rounded-lg mb-4 bg-red-100 text-red-700';
                messageDiv.innerHTML = '检查更新失败: ' + error.message;
            });
        }
        
        // 应用加载完成后自动检测更新
        function checkUpdateOnLoad() {
            console.log('开始自动检测更新');
            fetch('/api/check-update').then(response => {
                console.log('更新检查响应状态:', response.status);
                return response.json();
            }).then(data => {
                console.log('更新检查结果:', data);
                // 只有在检测到更新时才显示通知
                if (data.update_available) {
                    console.log('发现更新，显示通知');
                    // 创建更新通知元素
                    const notification = document.createElement('div');
                    notification.style.position = 'fixed';
                    notification.style.top = '20px';
                    notification.style.right = '20px';
                    notification.style.backgroundColor = '#FEF3C7';
                    notification.style.borderLeft = '4px solid #FBBF24';
                    notification.style.color = '#92400E';
                    notification.style.padding = '16px';
                    notification.style.borderRadius = '8px';
                    notification.style.boxShadow = '0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06)';
                    notification.style.zIndex = '9999';
                    notification.style.maxWidth = '300px';
                    notification.innerHTML = `
                        <div style="display: flex; align-items: center;">
                            <div style="flex-shrink: 0; margin-right: 12px;">
                                <i class="fa fa-bell" style="color: #F59E0B; font-size: 20px;"></i>
                            </div>
                            <div style="flex: 1;">
                                <p style="font-size: 14px; font-weight: 500; margin: 0 0 4px 0;">发现新版本</p>
                                <p style="font-size: 14px; margin: 4px 0;">当前版本: ${data.current_version}</p>
                                <p style="font-size: 14px; margin: 4px 0;">最新版本: ${data.latest_version}</p>
                                <p style="font-size: 14px; margin: 8px 0 0 0;">请前往官网下载更新</p>
                            </div>
                            <button onclick="this.parentElement.parentElement.remove()" style="background: none; border: none; color: #F59E0B; cursor: pointer;">
                                <i class="fa fa-times"></i>
                            </button>
                        </div>
                    `;
                    
                    // 添加到页面
                    console.log('添加通知到页面');
                    document.body.appendChild(notification);
                    console.log('通知添加成功');
                    
                    // 5秒后自动关闭
                    setTimeout(() => {
                        console.log('自动关闭通知');
                        notification.remove();
                    }, 5000);
                } else {
                    console.log('没有发现更新');
                }
            }).catch(error => {
                // 自动检测更新失败时不显示错误信息，避免打扰用户
                console.log('自动检测更新失败:', error);
            });
        }
        
        // 初始化应用
        window.onload = init;
    </script>
</body>
</html>
'''

# 启动Flask服务器
def start_flask_server():
    """启动Flask服务器"""
    app.run(host='127.0.0.1', port=5000, debug=False, use_reloader=False)

# 主函数
def main():
    """主函数"""
    # 启动Flask服务器线程
    flask_thread = threading.Thread(target=start_flask_server, daemon=True)
    flask_thread.start()

    # 等待Flask服务器启动
    time.sleep(1)

    # 创建webview窗口
    webview.create_window(
        APP_NAME,
        url='http://127.0.0.1:5000',
        width=1000,
        height=700,
        resizable=True
    )

    # 启动webview
    webview.start()

if __name__ == '__main__':
    main()
