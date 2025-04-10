# -*- coding: utf-8 -*-
import requests
from bs4 import BeautifulSoup
from datetime import datetime

def get_transit_info(
    departure_station: str,
    destination_station: str,
    search_type: int = 1,  # 1: 出発時間基準, 4: 到着時間基準
    use_today: bool = True,
    month: str = "",
    day: str = "",
    hour: str = "08",
    minute: str = "00"
) -> str:
    """
    Yahoo路線情報から乗換案内を取得する

    Returns:
        経路情報を整形した文字列
    """

    # 年は固定（例：2025）
    year = "2025"

    if use_today:
        today = datetime.today()
        month = today.strftime("%m")
        day = today.strftime("%d")
    else:
        month = month.zfill(2)
        day = day.zfill(2)

    hour = hour.zfill(2)
    minute = minute.zfill(2)
    m1 = minute[0]
    m2 = minute[1]

    # URL構築
    route_url = (
        "https://transit.yahoo.co.jp/search/print?"
        f"from={departure_station}&to={destination_station}"
        f"&type={search_type}&y={year}&m={month}&d={day}&hh={hour}&m1={m1}&m2={m2}"
    )

    try:
        response = requests.get(route_url)
        soup = BeautifulSoup(response.text, 'html.parser')

        route_summary = soup.find("div", class_="routeSummary")
        required_time = route_summary.find("li", class_="time").get_text()
        transfer_count = route_summary.find("li", class_="transfer").get_text()
        fare = route_summary.find("li", class_="fare").get_text()

        result = f"====== {departure_station} → {destination_station} ======\n"
        result += f"🕒 所要時間：{required_time}\n"
        result += f"🔄 {transfer_count}\n"
        result += f"💴 料金：{fare}\n"

        route_detail = soup.find("div", class_="routeDetail")
        stations = [s.get_text().strip() for s in route_detail.find_all("div", class_="station")]
        lines = [l.find("div").get_text().strip() for l in route_detail.find_all("li", class_="transport")]
        estimated_times = [et.get_text() for et in route_detail.find_all("li", class_="estimatedTime")]
        fars = [f.get_text().strip() for f in route_detail.find_all("p", class_="fare")]

        result += "\n====== 🚉 乗り換え情報 ======\n"
        for i in range(len(lines)):
            result += f"【{i+1}】{stations[i]}\n"
            result += f"  └🚆 {lines[i]}（所要時間: {estimated_times[i]}, 料金: {fars[i]}）\n"
        result += f"【到着】{stations[-1]}"

        return result

    except Exception as e:
        return f"❌ エラーが発生しました：{str(e)}"