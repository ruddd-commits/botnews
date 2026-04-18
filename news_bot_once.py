from news_bot import validate_config, fetch_and_send
import logging, sys, traceback, time

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)

def main():
    try:
        logging.info("🚀 Bot starting...")

        validate_config()
        logging.info("✅ Config valid")

        fetch_and_send()
        logging.info("✅ Fetch & send selesai")

    except Exception as e:
        logging.error("❌ ERROR TERJADI!")
        logging.error(str(e))

        # detail traceback (penting banget buat debug)
        traceback.print_exc()

        # exit non-zero → supaya GitHub Actions tahu ini gagal
        sys.exit(1)

    finally:
        logging.info("🛑 Bot finished")

if __name__ == "__main__":
    main()
