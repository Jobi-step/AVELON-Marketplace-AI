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
    st.success("Данные получены. Следующим этапом подключим генерацию карточки.")