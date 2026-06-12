import requests, time


def create_post(user_id, token, text, image_url=None, reply_to_id=None):
    create_url = f"https://graph.threads.net/v1.0/{user_id}/threads"
    publish_url = f"https://graph.threads.net/v1.0/{user_id}/threads_publish"

    # -----------------------
    # payload生成
    # -----------------------
    if image_url:
        payload = {
            "media_type": "IMAGE",
            "image_url": image_url,
            "text": text,
            "access_token": token,
        }
    else:
        payload = {
            "media_type": "TEXT",
            "text": text,
            "access_token": token,
        }

    # reply_to_idがある場合はpayloadに追加
    if reply_to_id:
        payload["reply_to_id"] = reply_to_id

    # -----------------------
    # create
    # -----------------------
    
    # createのレスポンスをresとして受け取るように変更
    create_res = requests.post(create_url, data=payload)
    
    # createのレスポンスが200以外の場合は失敗とみなす
    if create_res.status_code != 200:
        print("create failed:", create_res.text)
        return None

    # レスポンスからcreation_idを抽出
    creation_id = create_res.json().get("id")

    # creation_idがない場合は失敗とみなす
    if not creation_id:
        print("❌ creation_id missing:", create_res.text)
        return None

    time.sleep(1.5)

    # -----------------------
    # publish
    # -----------------------
    #
    
    # publishのレスポンスをresとして受け取るように変更
    publish_res = requests.post(
        publish_url,
        data={"creation_id": creation_id, "access_token": token},
    )
    
    # publishのレスポンスが200以外の場合は失敗とみなす
    if publish_res.status_code != 200:
        print("publish failed:", publish_res.text)
        return None

    # publishのレスポンスからmedia_idを抽出して返すように変更
    publish_data = publish_res.json()
    media_id = publish_data.get("id")


    return {
        "creation_id": creation_id,
        "media_id": media_id,
        "raw": publish_data,
        "is_reply": bool(reply_to_id),
    }
