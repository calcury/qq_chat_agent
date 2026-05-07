from flask import Flask, request, jsonify, render_template
import json
import os
import re
from zhipuai import ZhipuAI

app = Flask(__name__)

ORIGIN = ""  # your file folder
API_KEY = ""  # your API key
CONFIG_DIR = "config"
ACCOUNTS_PATH = os.path.join(CONFIG_DIR, "accounts.json")
CONTENT_PATH = os.path.join(CONFIG_DIR, "content.json")
ASSETS_PATH = os.path.join(CONFIG_DIR, 'assets.json')
HISTORY_PATH = os.path.join(CONFIG_DIR, "history.json")

# --- 工具函数 ---


def save_json(path, data):
    if not os.path.exists(CONFIG_DIR):
        os.makedirs(CONFIG_DIR)
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4, ensure_ascii=False)


def load_json(path, default):
    if not os.path.exists(path) or os.stat(path).st_size == 0:
        save_json(path, default)
        return default
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except:
        return default


def manage_history(target_id, role, content, max_len=20):
    history = load_json(HISTORY_PATH, {})
    if target_id not in history:
        history[target_id] = []

    # Append new message
    history[target_id].append({"role": role, "content": content})

    # Keep only the last N messages
    if len(history[target_id]) > max_len:
        history[target_id] = history[target_id][-max_len:]

    save_json(HISTORY_PATH, history)
    return history[target_id]


client = ZhipuAI(api_key=API_KEY)

debug_data = [0, 1]


@app.route('/debug')
def debug():
    return debug_data


@app.route('/webhook', methods=['POST'])
def webhook():
    data = request.json
    debug_data[0] = data
    if not data:
        return jsonify({}), 200

    accounts = load_json(ACCOUNTS_PATH, {})
    content = load_json(CONTENT_PATH, {})
    assets_data = load_json(ASSETS_PATH, {})

    msg_type = data.get('message_type')
    group_id = str(data.get('group_id', ''))
    user_id = str(data.get('user_id', ''))
    target_id = group_id if msg_type == 'group' else user_id
    raw_message = data.get('raw_message', '')
    self_id = str(data.get('self_id'))

    acc_cfg = accounts.get(target_id)
    if not acc_cfg or not acc_cfg.get('enabled'):
        return jsonify({}), 200

    clean_message = re.sub(r'\[CQ:[^\]]+\]', '', raw_message).strip()
    if not clean_message:
        return jsonify({}), 200

    current_history = manage_history(target_id, "user", raw_message)

    is_at = f"[CQ:at,qq={self_id}]" in raw_message
    at_list = re.findall(r'\[CQ:at,qq=(\d+)\]', raw_message)
    at_others = any(qq != self_id for qq in at_list)

    for g_name in acc_cfg.get('groups', []):
        replies = content.get(g_name, {}).get('replies', {})
        for trigger, reply in replies.items():
            if trigger and trigger in clean_message:
                return jsonify({"reply": reply, "at_sender": True}), 200

    # 接入 AI & Agent
    ai_enabled = acc_cfg.get('ai_enabled', False)
    reply_mode = acc_cfg.get('reply_mode', 'at')  # at, always, agent
    if acc_cfg.get('assets_enabled') and not at_others:
        asset_reply_mode = acc_cfg.get('asset_reply_mode', 'at')
        should_check_assets = (asset_reply_mode == 'always') or (
            asset_reply_mode == 'at' and is_at)

        if should_check_assets:
            try:
                selected_assets = acc_cfg.get('selected_assets', [])

                if not selected_assets:
                    pass
                else:
                    asset_list_for_ai = []
                    index_map = {}
                    global_idx = 0

                    for name in selected_assets:
                        target_data = assets_data.get(name, [])

                        if isinstance(target_data, list):
                            for item in target_data:
                                index_map[str(global_idx)] = item
                                asset_list_for_ai.append(
                                    f"索引[{global_idx}]: {item.get('desc', '无描述')} (来自库:{name})")

                    asset_context = "\n".join(asset_list_for_ai)
                    history_text = ""
                    for msg in current_history[:-1]:
                        role_label = "助手" if msg['role'] == 'assistant' else "用户"
                        history_text += f"{role_label}: {msg['content']}\n"

                    asset_prompt = (
                        f"你是素材库调度员。以下是可选素材及其【触发场景】：\n{asset_context}\n\n"
                        f"【历史对话预览】：\n{history_text if history_text else '（无历史记录）'}\n"
                        f"【当前用户消息】：'{clean_message}'\n\n"
                        f"【决策准则】：\n"
                        f"[你的QQ号是2329908485] \n"
                        f"1. 形式判定：判断用户是需要具体的【资料/文件】，还是更希望与你进行【文字交流】。如果用户明显是在寻求聊天、建议、安慰或解释，而不是单纯要资源，请务必返回 'no'，将对话交给 AI 回复。\n"
                        f"2. 触发频率限制：如果是【纯聊天】，若历史显示近期已频繁发送过素材，请返回 'no' 以免打扰；如果是【特定答疑】，请精准匹配需求。\n"
                        f"3. 拒绝重复：若历史显示该素材近期刚被触发过，除非用户有明确的新需求，否则返回 'no'。\n"
                        f"4. 契合度：只有当消息与素材的【触发场景】契合时才返回索引。\n\n"
                        f"任务：判断是否命中。回复要求：数字 或 'no'。严禁解释。"
                    )

                    # 调用 AI 进行意图识别
                    res = client.chat.completions.create(
                        model="glm-4-flash",
                        messages=[{"role": "user", "content": asset_prompt}],
                        max_tokens=10,
                        temperature=0.1,
                        timeout=10
                    )

                    asset_result = res.choices[0].message.content.strip()
                    print(f"DEBUG: 调度员判定结果 -> {asset_result}")
                    debug_data[1] = asset_result
                    if asset_result.isdigit() and asset_result in index_map:
                        hit_item = index_map[asset_result]
                        file_name = hit_item.get('path', '')
                        file_type = hit_item.get('type', 'file')
                        if file_name.startswith(('http://', 'https://')):
                            full_url = file_name
                        else:
                            base_url = ORIGIN
                            full_url = base_url + file_name

                        if file_type == 'image':
                            return jsonify({
                                "reply": [
                                    {
                                        "type": "image",
                                        "data": {
                                            "file": full_url
                                        }
                                    }
                                ],
                                "auto_escape": False
                            }), 200
                        elif file_type == 'file':
                            return jsonify({
                                "reply": [
                                    {
                                        "type": "file",
                                        "data": {
                                            "path": full_url,
                                            "name": file_name
                                        }
                                    }
                                ],
                                "auto_escape": False
                            }), 200
                        elif file_type == 'video':
                            return jsonify({
                                "reply": [
                                    {
                                        "type": "file",
                                        "data": {
                                            "path": full_url,
                                            "name": file_name
                                        }
                                    }
                                ],
                                "auto_escape": False
                            }), 200
                        elif file_type == 'text':
                            return jsonify({
                                "reply": file_name,
                                "at_sender": True,
                                "auto_escape": False
                            }), 200
                        else:
                            return jsonify({"reply": "脑子有点乱..."}), 200
            except Exception as e:
                print(f"素材库逻辑运行出错: {e}")

    if ai_enabled:
        should_reply = False
        if is_at:
            should_reply = True
        if reply_mode == 'at' and is_at:
            should_reply = True
        elif reply_mode == 'always':
            should_reply = True
        elif reply_mode == 'agent':
            agent_condition = acc_cfg.get('agent_condition', '用户在向你提问')

            history_text = ""
            for msg in current_history[:-1]:
                role_name = "助手" if msg['role'] == 'assistant' else "用户"
                history_text += f"{role_name}: {msg['content']}\n"

                decision_prompt = f"""你是一个对话决策助手。
                请分析【历史对话】和【当前消息】，判断助手是否应该参与回复。
                [你的QQ号是2329908485]

                请严格按照以下【优先级】逻辑进行判定：

                1. 特定触发（最高优先级）：
                   - 若当前消息符合回复条件：[{agent_condition}]，或明确在向你提问、寻求你的功能支持，请务必返回 'yes'。

                2. 避让原则：
                   - 若用户明显正在与其他人类成员交谈，或对话话题与你无关，请务必返回 'no'（除非满足上述“特定触发”）。

                3. **场景允许（基础逻辑）**：
                   - 若当前消息是与你（助手）上一轮对话的直接延续，或表现出“被助手回复”的需求，返回 'yes'。
                   - 拒绝标准：纯乱码、刷屏、或内容完全不包含任何需要回应的语义，返回 'no'。

                4. 若用户表现出不需要你的回复,或者不理你的回复请暂时停止交谈

                【历史对话】：
                {history_text if history_text else "（无历史记录）"}

                【当前用户消息】：
                "{clean_message}"

                任务：综合评估。如果满足特定触发或需要你介入回复则返回 'yes'，若判定为他人聊天或无须插话则返回 'no'。严格只返回一个单词。"""

            try:
                decision_res = client.chat.completions.create(
                    model="glm-4-flash",
                    messages=[{"role": "user", "content": decision_prompt}],
                    max_tokens=5,
                    temperature=0.1
                )
                decision = decision_res.choices[0].message.content.strip(
                ).lower()
                print(f"Agent 决策结果: {decision}")
                if 'yes' in decision:
                    should_reply = True
            except Exception as e:
                print(f"Agent Decision Error: {e}")

        if should_reply and not at_others:
            try:
                system_prompt = acc_cfg.get(
                    'ai_prompt') or "你是一个助手。" + "回复内容禁止包含链接"
                messages_for_api = [
                    {"role": "system", "content": system_prompt}]
                messages_for_api.extend(current_history)

                response = client.chat.completions.create(
                    model="glm-4-flash",
                    messages=messages_for_api
                )
                ai_reply = response.choices[0].message.content
                manage_history(target_id, "assistant", ai_reply)

                return jsonify({"reply": ai_reply, "at_sender": True}), 200
            except Exception as e:
                print(f"AI Reply Error: {e}")
                return jsonify({"reply": "脑子有点乱..."}), 200

    return jsonify({}), 200


@app.route('/')
def index():
    return render_template('admin.html')


@app.route('/api/config', methods=['GET'])
def get_config():
    return jsonify({
        "accounts": load_json(ACCOUNTS_PATH, {}),
        "content": load_json(CONTENT_PATH, {})
    })


@app.route('/api/accounts', methods=['POST'])
def save_accounts():
    data = request.json
    save_json(ACCOUNTS_PATH, data)
    return jsonify({"status": "success"})


@app.route('/api/content', methods=['POST'])
def save_content():
    data = request.json
    save_json(CONTENT_PATH, data)
    return jsonify({"status": "success"})


@app.route('/assets')
def assets_ui():
    return render_template('assets.html')


@app.route('/api/assets', methods=['GET', 'POST'])
def handle_assets():
    if request.method == 'GET':
        return jsonify(load_json(ASSETS_PATH, {}))
    else:
        data = request.json
        save_json(ASSETS_PATH, data)
        return jsonify({"status": "success"})
