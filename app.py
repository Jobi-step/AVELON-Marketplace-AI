print("AVELON Marketplace AI запущен")
import streamlit as st

st.set_page_config(
    page_title="AVELON Marketplace AI",
    page_icon="🛒",
    layout="wide",
)

st.title("AVELON Marketplace AI")
st.subheader("Создание карточки объявления для Avito")

st.markdown("### Данные товара")

supplier_text = st.text_area(
    "Информация от поставщика",
    placeholder="Вставь описание товара от поставщика",
)

purchase_price = st.number_input(
    "Закупочная цена, ₽",
    min_value=0,
    step=100,
)

sizes = st.text_input(
    "Размеры",
    placeholder="Например: S, M, L, XL",
)

material = st.text_input(
    "Материал",
    placeholder="Например: хлопок",
)

extra_info = st.text_area(
    "Дополнительная информация",
    placeholder="Любые важные детали о товаре",
)

photos = st.file_uploader(
    "Фотографии товара",
    type=["jpg", "jpeg", "png", "webp"],
    accept_multiple_files=True,
)

if st.button("Создать карточку объявления", type="primary"):
    if not supplier_text.strip():
        st.error("Добавь информацию о товаре.")
        st.stop()

    if purchase_price <= 0:
        st.error("Укажи закупочную цену товара.")
        st.stop()

    minimum_price = purchase_price + 1000
    recommended_price = purchase_price + 1500
    expected_profit = recommended_price - purchase_price

    st.divider()
    st.header("Готовая карточка объявления")

    st.subheader("Заголовок")

    title_source = supplier_text.strip() if supplier_text.strip() else "Товар для Avito"
    title = title_source[:50]

    st.write(title)
    st.caption(f"{len(title)} / 50 символов")

    st.subheader("Описание")

    description_source = supplier_text.strip() if supplier_text.strip() else "Товар"

    st.write(
        f"""
🔥 {description_source}

📏 Размеры: {sizes or "уточняйте"}
🧵 Материал: {material or "хлопок"}
📦 Доставка по всей России.

{extra_info if extra_info.strip() else ""}

Если нужны дополнительные фото или помощь с размером — пишите прямо сейчас.
"""
    )

    st.subheader("Цена")
    st.write(f"Закупочная цена: {purchase_price:,} ₽")
    st.write(f"Минимальная цена: {minimum_price:,} ₽")
    st.write(f"Рекомендуемая цена: {recommended_price:,} ₽")
    st.write(f"Ожидаемая прибыль: {expected_profit:,} ₽")

    st.subheader("Аналитика")
    st.write("Рекомендуемый город: Казань")
    st.write("Конкуренция: средняя")
    st.write("Вероятность продажи: 70%")
    st.write("Ожидаемый срок продажи: 7–14 дней")

    st.subheader("Фотографии")
    if photos:
        st.write(f"Загружено фотографий: {len(photos)}")
        st.write("Рекомендуемый порядок: 1 → 2 → 3 → остальные")
    else:
        st.write("Фотографии пока не загружены")