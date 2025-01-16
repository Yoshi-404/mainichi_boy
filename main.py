from typing import Final
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler
import unicodedata
from datetime import datetime, timedelta, timezone, time
import logging
import jpholiday
import requests
import pandas as pd
import asyncio
from bs4 import BeautifulSoup
from PIL import Image, ImageDraw, ImageFont

# ログ設定
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

TOKEN: Final = 'Your_bot_token'
BOT_USERNAME: Final = '@your_bot_name'

# バススケジュールCSVファイルのパス
BUS_SCHEDULE_CSV: Final = "~/BUS_SCHEDULE_CSV.csv"

def normalize_text(text: str) -> str:
    return unicodedata.normalize('NFKC', text).lower()

async def fetch_train_info(url: str) -> str:
    """
    指定されたURLから電車の運行情報をスクレイピングする。
    :param url: 運行情報ページのURL
    :return: 路線名と運行情報のテキスト
    """
    try:
        # HTTPリクエストを送信してページを取得
        response = requests.get(url)
        response.raise_for_status()

        # BeautifulSoupでHTMLを解析
        soup = BeautifulSoup(response.text, 'html.parser')

        # og:titleメタタグから路線名を取得
        meta_title = soup.find('meta', property='og:title')
        route_name = meta_title['content'] if meta_title and meta_title.get('content') else "路線名不明"

        # og:descriptionメタタグから運行情報を取得
        meta_description = soup.find('meta', property='og:description')
        train_info = meta_description['content'] if meta_description and meta_description.get('content') else "運行情報不明"

        return f"{route_name}\n{train_info}"
    except Exception as e:
        logger.error(f"運行情報の取得中にエラーが発生しました: {e}")
        return "運行情報の取得中にエラーが発生しました。"

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text('こんにちは！あなたの毎日を管理します、マイニチです！')
        # 運行情報を取得
    train_info_1 = await fetch_train_info("https://transit.yahoo.co.jp/diainfo/274/0")  # 例: JR阪和線
    train_info_2 = await fetch_train_info("https://transit.yahoo.co.jp/diainfo/339/0")  # 例: 南海本線

    # 運行情報を表示
    train_info_message = f"現在の電車運行情報:\n\n{train_info_1}\n\n{train_info_2}"
    await update.message.reply_text(train_info_message)

    await update.message.reply_text('コマンド一覧:\n/help - ヘルプを表示\n/clean - チャット履歴消去\n/bus - バスの時刻表確認\n/holidays - 今日が祝日かどうかを表示\n/weather - 和歌山県北部の天気予報を表示\n/set_weather_reminder - 毎朝7時に天気予報を送信\n/unset_weather_reminder - 天気予報リマインダーを解除')

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text('マイニチです！何かを入力してください！')

async def clean_chat(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    keyboard = [
        [
            InlineKeyboardButton("はい", callback_data="clean_chat_confirm"),
            InlineKeyboardButton("いいえ", callback_data="cancel")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text('チャット履歴を消しますか？', reply_markup=reply_markup)

async def clean_chat_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()  # 必ず最初にクエリに応答する

    chat_id = query.message.chat_id
    try:
        # メッセージIDを逆順で削除（例として最大10件削除）
        last_message_id = query.message.message_id
        delete_count = 0
        for message_id in range(last_message_id, last_message_id - 50, -1):  # 過去100件を削除対象
            try:
                await context.bot.delete_message(chat_id=chat_id, message_id=message_id)
                deleted_count += 1
            except Exception as e:
                logger.warning(f"メッセージ削除失敗 (message_id={message_id}): {e}")
        
        await query.message.reply_text("チャット履歴をすべて削除しました！（最新から最大50件）")
    except Exception as e:
        logger.error(f"チャット履歴削除中にエラー: {e}")
        await query.message.reply_text("チャット履歴の削除中にエラーが発生しました。")

async def get_weather() -> str:
    """
    気象庁APIから天気予報を取得し、気温や降水確率を含めてフォーマットして返す。
    """
    try:
        # 気象庁天気予報API（和歌山県エリアコード: 300000）
        JSON_URL = "https://www.jma.go.jp/bosai/forecast/data/forecast/300000.json"
        response = requests.get(JSON_URL)
        response.raise_for_status()

        # JSONデータを取得
        jma_data = response.json()

        # 和歌山県北部のエリアデータを取得
        area_data = next(area for area in jma_data[0]["timeSeries"][0]["areas"] if area["area"]["name"] == "北部")

        # 天気予報
        weather_today = area_data["weathers"][0]
        wind_today = area_data["winds"][0]
        wave_today = area_data["waves"][0]

        # 降水確率（北部）
        precip_data = next(area for area in jma_data[0]["timeSeries"][1]["areas"] if area["area"]["name"] == "北部")
        precip_chances = precip_data["pops"]

        # 気温（和歌山市）
        temp_data = next(area for area in jma_data[0]["timeSeries"][2]["areas"] if area["area"]["name"] == "和歌山")
        temp_min = temp_data["temps"][0]
        temp_max = temp_data["temps"][1]

        # 結果をフォーマット
        return (
            f"【和歌山県北部の天気予報】\n"
            f"天気: {weather_today}\n"
            f"気温: {temp_min}°C ～ {temp_max}°C\n"
            f"降水確率: {' / '.join(precip_chances)}%\n"
            f"風: {wind_today}\n"
            f"波: {wave_today}"
        )
    except Exception as e:
        logger.error(f"天気予報取得中にエラー: {e}")
        return "天気予報の取得中にエラーが発生しました。"

async def weather(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    /weather コマンドで天気予報を表示する。
    """
    weather_info = await get_weather()
    await update.message.reply_text(weather_info)

async def holidays(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    dt_now_jst_aware = datetime.now(timezone(timedelta(hours=9)))
    if jpholiday.is_holiday(dt_now_jst_aware.date()):
        await update.message.reply_text('今日は祝日です！')
    else:
        await update.message.reply_text('今日は平日です！')
    
    keyboard = [
        [
            InlineKeyboardButton("今年の祝日一覧を確認する", callback_data="show_holidays"),
            InlineKeyboardButton("キャンセル", callback_data="cancel")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text('今年の祝日一覧を確認しますか？', reply_markup=reply_markup)

async def show_holidays(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()  # 必ず最初に応答

    # 現在の年の祝日一覧を取得
    dt_now_jst_aware = datetime.now(timezone(timedelta(hours=9)))
    current_year = dt_now_jst_aware.year
    all_holidays = jpholiday.year_holidays(current_year)

    # 祝日情報をフォーマット
    holidays_text = "今年の祝日一覧:\n" + "\n".join([f"{date}: {name}" for date, name in all_holidays])

    # メッセージを送信
    await query.message.reply_text(holidays_text)

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    await query.message.reply_text("操作をキャンセルしました。")

async def bus_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    dt_now_jst_aware = datetime.now(timezone(timedelta(hours=9)))
    await update.message.reply_text(dt_now_jst_aware.strftime('現在時刻は %Y年%m月%d日 %H:%M:%Sです！'))
    keyboard = [
        [
            InlineKeyboardButton("貴志", callback_data="to_kishi"),
            InlineKeyboardButton("和歌山大学前駅", callback_data="to_wakayama_university_station"),
            InlineKeyboardButton("和歌山大学", callback_data="to_wakayama_university"),
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text('目的地のバス停を選択してください', reply_markup=reply_markup)

async def bus_going(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()  # 必ず最初にクエリに応答する

    if query.data == "to_kishi":
        keyboard = [
            [
                InlineKeyboardButton("和歌山大学前駅", callback_data="from_貴志_和歌山大学前駅"),
                InlineKeyboardButton("和歌山大学", callback_data="from_貴志_和歌山大学"),
            ]
        ]
        await query.edit_message_text("貴志からの出発地を選択してください：", reply_markup=InlineKeyboardMarkup(keyboard))

    elif query.data == "to_wakayama_university_station":
        keyboard = [
            [
                InlineKeyboardButton("貴志", callback_data="from_和歌山大学前駅_貴志"),
                InlineKeyboardButton("和歌山大学", callback_data="from_和歌山大学前駅_和歌山大学"),
            ]
        ]
        await query.edit_message_text("和歌山大学前駅からの出発地を選択してください：", reply_markup=InlineKeyboardMarkup(keyboard))

    elif query.data == "to_wakayama_university":
        keyboard = [
            [
                InlineKeyboardButton("貴志", callback_data="from_和歌山大学_貴志"),
                InlineKeyboardButton("和歌山大学前駅", callback_data="from_和歌山大学_和歌山大学前駅"),
            ]
        ]
        await query.edit_message_text("和歌山大学からの出発地を選択してください：", reply_markup=InlineKeyboardMarkup(keyboard))

    else:
        logger.error(f"Unexpected callback data: {query.data}")
        await query.edit_message_text("選択肢にありません。もう一度お試しください。")

async def bus_schedule_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    try:
        # 現在時刻と曜日を取得
        now = datetime.now()
        is_weekend = now.weekday() >= 5  # 土日祝日判定

        # CSV読み込み
        df = pd.read_csv(BUS_SCHEDULE_CSV, delimiter=';')
        df['発車地点'] = df['発車地点'].str.strip()
        df['到着地点'] = df['到着地点'].str.strip()

        # クエリデータの取得
        query = update.callback_query
        if not query:
            logger.error("Callback query is missing")
            return

        query_data = query.data.split('_')
        if len(query_data) != 3:
            await query.message.reply_text("無効なクエリデータです。")
            return

        departure, destination = query_data[1].strip(), query_data[2].strip()
        logger.info(f"Departure: {departure}, Destination: {destination}")

        # 発車地点と到着地点でフィルタリング
        filtered_df = df[(df['発車地点'] == departure) & (df['到着地点'] == destination)]
        if filtered_df.empty:
            logger.error(f"No schedule found for route: {departure} -> {destination}")
            await query.message.reply_text("指定されたルートのスケジュールが見つかりませんでした。")
            return

        # 適切な列を選択
        time_column = '祝日時間' if jpholiday.is_holiday(now.date()) else ('土日時間' if is_weekend else '平日時間')
        times_raw = filtered_df[time_column].iloc[0].split('|')

        # 時間データを検証してクリーンアップ
        times = []
        for time in times_raw:
            try:
                parsed_time = datetime.strptime(time.strip(), '%H:%M').time()
                times.append(parsed_time)
            except ValueError:
                logger.warning(f"Invalid time format skipped: {time}")

        # 現在時刻以降のバス時間を取得
        next_buses = [time.strftime('%H:%M') for time in times if time > now.time()]

        # 次の3つのバス時間を取得
        next_buses = next_buses[:3]

        if next_buses:
            bus_schedule_text = f"次の3つのバス時間 ({departure} -> {destination}):\n" + "\n".join(next_buses)
        else:
            bus_schedule_text = f"現在、{departure} -> {destination} の次のバスはありません。"

        await query.message.reply_text(bus_schedule_text)
    except Exception as e:
        logger.error(f"Error in bus_schedule_command: {e}")
        if update.callback_query:
            await update.callback_query.message.reply_text("バススケジュールの取得中にエラーが発生しました。")

async def set_weather_reminder(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    リマインダーを設定する。
    毎朝7時に天気予報を送信する。
    """
    try:
        # 毎朝7時に実行するジョブを登録
        reminder_time = time(7, 0, 0)  # 07:00
        context.job_queue.run_daily(send_daily_weather, reminder_time, data=update.effective_chat.id, name=str(update.effective_chat.id))
        
        await update.message.reply_text("毎朝7時に天気予報をお届けします！")
    except Exception as e:
        logger.error(f"リマインダー設定中にエラーが発生しました: {e}")
        await update.message.reply_text("リマインダー設定中にエラーが発生しました。")

async def send_daily_weather(context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    毎朝天気予報を送信するジョブ。
    """
    try:
        weather_info = await get_weather()
        chat_id = context.job.data  # `data`からチャットIDを取得
        await context.bot.send_message(chat_id, text=weather_info)
    except Exception as e:
        logger.error(f"天気予報送信中にエラーが発生しました: {e}")

async def unset_weather_reminder(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    リマインダーを削除する。
    """
    current_jobs = context.job_queue.get_jobs_by_name(str(update.effective_chat.id))
    if not current_jobs:
        await update.message.reply_text("リマインダーは設定されていません。")
        return

    for job in current_jobs:
        job.schedule_removal()
    
    await update.message.reply_text("リマインダーを解除しました。")








if __name__ == '__main__':
    print('Starting bot...')
    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler('start', start_command))
    app.add_handler(CommandHandler('help', help_command))
    app.add_handler(CommandHandler('clean', clean_chat))
    app.add_handler(CallbackQueryHandler(clean_chat_confirm, pattern="^clean_chat_confirm$"))
    app.add_handler(CommandHandler('bus', bus_command))
    app.add_handler(CommandHandler('holidays', holidays))
    app.add_handler(CommandHandler('weather', weather))
    app.add_handler(CommandHandler('set_weather_reminder', set_weather_reminder))  # リマインダー登録
    app.add_handler(CommandHandler('unset_weather_reminder', unset_weather_reminder))  # リマインダー解除
    app.add_handler(CallbackQueryHandler(cancel, pattern="^cancel$"))
    app.add_handler(CallbackQueryHandler(show_holidays, pattern="^show_holidays"))
    app.add_handler(CallbackQueryHandler(bus_going, pattern="^to_"))
    app.add_handler(CallbackQueryHandler(bus_schedule_command, pattern="^from_"))

    print('Polling...')
    app.run_polling(poll_interval=2)
