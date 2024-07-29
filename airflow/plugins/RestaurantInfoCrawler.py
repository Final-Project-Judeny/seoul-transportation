from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import WebDriverException
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

# web driver에 연결(실패시 재시도)하는 함수
def get_webdriver(remote_webdriver, options, retries=3, delay=5):
    driver = None
    for attempt in range(retries):
        try:
            driver = webdriver.Remote(f'http://{remote_webdriver}:4444/wd/hub', options=options)
            break
        except WebDriverException as e:
            logging.error(f"Webdriver connection attempt {attempt + 1} failed: {e}")
            if attempt < retries - 1:
                time.sleep(delay) # 잠시 대기 후 재시도
            else:
                raise  # 모든 재시도 실패 시 예외 발생
    return driver

# 다이닝코드에서 서울의 음식점 정보 크롤링하는 함수
def RestaurantInfoCrawler(args):
    options = webdriver.ChromeOptions()
    options.add_argument('--headless') # 브라우저 숨김
    options.add_argument('--disable-gpu') # GPU 하드웨어 가속 미사용
    options.add_argument('--no-sandbox') # 샌드박스 모드 비활성화
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument('--remote-debugging-port=9222')  # 디버깅 포트 추가
    options.add_argument('--window-size=1920x1080')  # 브라우저 창 크기 설정
    options.add_argument(f'user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_3) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/80.0.3987.87 Safari/537.36') # user-agent를 수정해 웹 사이트의 차단을 완화
    options.add_argument('--disable-extensions')  # 확장 프로그램 비활성화
    options.add_argument('--disable-software-rasterizer')  # 소프트웨어 래스터라이저 비활성화
    options.add_argument('--no-zygote')  # zygote 프로세스 사용 안함
    options.add_argument('--single-process')  # 단일 프로세스 모드
    options.add_argument('--disable-background-timer-throttling')  # 백그라운드 타이머 제한 비활성화
    options.add_argument('--disable-backgrounding-occluded-windows')  # 백그라운드 창 비활성화
    options.add_argument('--disable-breakpad')  # 브레이크패드 비활성화
    options.add_argument('--disable-client-side-phishing-detection')  # 피싱 감지 비활성화
    options.add_argument('--disable-component-update')  # 구성 요소 업데이트 비활성화
    options.add_argument('--disable-default-apps')  # 기본 앱 비활성화
    options.add_argument('--disable-hang-monitor')  # 행 모니터 비활성화
    options.add_argument('--disable-ipc-flooding-protection')  # IPC 홍수 보호 비활성화
    options.add_argument('--disable-popup-blocking')  # 팝업 차단 비활성화
    options.add_argument('--disable-prompt-on-repost')  # 재게시 시 프롬프트 비활성화
    options.add_argument('--disable-renderer-backgrounding')  # 렌더러 백그라운드 비활성화
    options.add_argument('--disable-sync')  # 동기화 비활성화
    options.add_argument('--metrics-recording-only')  # 메트릭 기록 전용
    options.add_argument('--mute-audio')  # 오디오 음소거
    options.add_argument('--no-first-run')  # 첫 실행 아님
    options.add_argument('--safebrowsing-disable-auto-update')  # 안전 브라우징 자동 업데이트 비활성화
    options.add_argument('--disable-3d-apis')  # 3D API 비활성화

    station_nm, line, district, num = args
    try:
        remote_webdriver = f'remote_chromedriver{num}'
        driver = get_webdriver(remote_webdriver, options)
        #driver = webdriver.Chrome(options=options)
    except Exception as e:
        logging.error(f"Webdriver connection is fail.: {e}")
        return

    url = "https://www.diningcode.com/list.dc?query="
    with driver:
        driver.get(url+encoding( f'{station_nm}역 {line}' ))

        # 로딩 대기
        try:
            WebDriverWait(driver, 10).until(
            lambda d: d.execute_script('return document.readyState') == 'complete'
        )
        except Exception as e:
            logging.error(f"Page load timeout: {e}")
            return

        # 크롤링 시작 시각
        crawl_timestamp = datetime.now().isoformat()

        # 맛집 로딩
        while True:
            try:
                # 더보기 버튼 로딩 대기 후 클릭
                more_button = WebDriverWait(driver, 3, poll_frequency=0.5).until(
                    EC.element_to_be_clickable((By.CSS_SELECTOR, '.SearchMore.upper'))
                )
                more_button.click()
            except:
                # 더보기 버튼이 없을 때 while문 종료
                logging.info("No more 'Load more' button.")
                break

        # 리스트, 지도에서 식당, 좌표 데이터 크롤링
        restaurant_elements = driver.find_elements(By.XPATH, '//a[contains(@class, "PoiBlock")]')
        map_elements = driver.find_elements(By.XPATH, '//a[@class="Marker"]')

        restaurants = []

        for i in range(min(len(restaurant_elements), len(map_elements))):
            restaurant = restaurant_elements[i]
            map = map_elements[i]
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

                # 좌표 추출
                x = map.get_attribute('data-lng')
                y = map.get_attribute('data-lat')

                # 식당 정보 저장
                restaurants.append({
                    'timestamp': crawl_timestamp,
                    'station': station_nm,
                    'district': district,
                    'name': name,
                    'score': score,
                    'category': category,
                    'hashtag': hashtag,
                    'image': image_url,
                    'loc_x': x,
                    'loc_y': y,
                })
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

        # JSON 문자열 생성
#        result = json.dumps(restaurants, ensure_ascii=False, indent=4)
        result = restaurants

        logging.info(f"JSON data for {station_nm} was successfully created.")

    return result


if __name__ == "__main__":
    test = RestaurantInfoCrawler('강남')
    print(test)
