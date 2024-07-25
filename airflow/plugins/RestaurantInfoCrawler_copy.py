from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time
import urllib.parse
import json
import logging
from datetime import datetime

# 로깅 설정
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


# 한글을 utf-8로 인코딩하는 함수
def encoding(input):
    return urllib.parse.quote(input, encoding='utf-8')

# 다이닝코드에서 서울의 음식점 정보 크롤링하는 함수
def RestaurantInfoCrawler(station_nm):
    options = webdriver.ChromeOptions()
    options.add_argument('--headless') # 브라우저 숨김
    options.add_argument('--disable-gpu') # GPU 하드웨어 가속 미사용
    options.add_argument('--no-sandbox') # 샌드박스 모드 비활성화
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument('--remote-debugging-port=9222')  # 디버깅 포트 추가
    options.add_argument('--window-size=1920x1080')  # 브라우저 창 크기 설정
    options.add_argument(f'user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_3) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/80.0.3987.87 Safari/537.36') # user-agent를 수정해 웹 사이트의 차단을 완화

    try:
        remote_webdriver = 'remote_chromedriver'
        driver = webdriver.Remote(f'http://{remote_webdriver}:4444/wd/hub', options=options)
        #driver = webdriver.Chrome(options=options)
    except Exception as e:
        logging.error(f"Webdriver connection is fail.: {e}")
        logging.error(driver.page_source)  # 페이지 소스 출력
        return

    url = "https://www.diningcode.com/list.dc?query="
    with driver:
        driver.get(url+encoding(station_nm+"역"))

        # 로딩 대기
        try:
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, '.SearchMore.upper'))
            )
        except Exception as e:
            logging.error(f"Page load timeout: {e}")
            return

        # 크롤링 시작 시각
        crawl_timestamp = datetime.now().isoformat()

        # 맛집 로딩
        while True:
            try:
                # 더보기 버튼 클릭
                more_button = WebDriverWait(driver, 10).until(
                    EC.element_to_be_clickable((By.CSS_SELECTOR, '.SearchMore.upper'))
                )
                more_button.click()
                # 몇 초간 대기
                time.sleep(1)
            except:
                # 더보기 버튼이 없을 때 while문 종료
                logging.info("No more 'Load more' button.")
                break

        restaurants = []

        # 리스트에서 식당 데이터 크롤링
        restaurant_elements = driver.find_elements(By.XPATH, '//a[contains(@class, "PoiBlock")]')

        for restaurant in restaurant_elements:
            try:
                # 이름 추출
                name_element = restaurant.find_element(By.XPATH, './/div[@class="InfoHeader"]')
                name = name_element.text[name_element.text.find(' ')+1:]

                # 리뷰평점 추출
                score = restaurant.find_element(By.XPATH, './/p[@class="Score"]').text # 점수

                cat_element = restaurant.find_element(By.XPATH, './/p[@class="Category"]')
                category = [cat.text for cat in cat_element.find_elements(By.XPATH, './/span')]

                # 해쉬태그 추출
                hash_element = restaurant.find_element(By.XPATH, './/div[@class="Hash"]')
                hashtag = [hash.text for hash in hash_element.find_elements(By.XPATH, './/span[not(@style)]')]

                # 이미지 추출 (없을 경우 예외 처리)
                try:
                    image_element = restaurant.find_element(By.XPATH, './/img[@class="title"]')
                    image_url = image_element.get_attribute('src')
                except:
                    image_url = None

                # 식당 정보 저장
                restaurants.append({
                    'name': name,
                    'score': score,
                    'category': category,
                    'hashtag': hashtag,
                    'image': image_url,
                })
            except Exception as e:
                logging.error(f"Error occurred: {e}")
                continue

        # 맵에서 좌표 데이터 크롤링
        map_elements = driver.find_elements(By.XPATH, '//a[@class="Marker"]')

        for i, map in enumerate(map_elements):
            try:
                # 좌표 추출
                x = map.get_attribute('data-lng')
                y = map.get_attribute('data-lat')

                # 좌표 정보 추가
                restaurants[i]['loc_x'] = x
                restaurants[i]['loc_y'] = y

            except Exception as e:
                logging.error(f"Error occurred: {e}")
                continue
        
        """
        # 결과 출력
        for i, restaurant in enumerate(restaurants):
            print(f'{i+1}.')
            for info in restaurants[i].keys():
                print(restaurants[i][info])
        """

        # 결과 데이터 구성
        result = {
            'timestamp': crawl_timestamp,
            'station': station_nm,
            'restaurants': restaurants
        }

        # JSON 문자열 생성
        result_json = json.dumps(result, ensure_ascii=False, indent=4)

        logging.info(f"JSON data for {station_nm} was successfully created.")

    return result_json


if __name__ == "__main__":
    test = RestaurantInfoCrawler('강남')
    print(test)
