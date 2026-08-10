print("AVELON Marketplace AI запущен")
import streamlit as st
from ai_client import generate_listing

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

extra_info = st.text_area(
    "Дополнительная информация",
    placeholder="Любые важные детали о товаре",
)

photos = st.file_uploader(
    "Фотографии товара",
    type=["jpg", "jpeg", "png", "webp"],
    accept_multiple_files=True,
)

if photos:
    st.markdown("### Предпросмотр фотографий")

    if len(photos) > 10:
        st.error("Можно загрузить максимум 10 фотографий.")
        st.stop()

    columns = st.columns(3)

    for index, photo in enumerate(photos):
        with columns[index % 3]:
            st.image(photo, caption=f"Фото {index + 1}", width="stretch")

if st.button("Создать карточку объявления", type="primary"):

    if not supplier_text.strip():
        st.error("Добавь информацию о товаре.")
        st.stop()

    if purchase_price <= 0:
        st.error("Укажи закупочную цену товара.")
        st.stop()

    if not photos:
        st.error("Добавь хотя бы одну фотографию товара.")
        st.stop()

    with st.spinner("AVELON анализирует товар..."):
            ai_result = generate_listing(
            supplier_text=supplier_text,
            purchase_price=purchase_price,
            extra_info=extra_info,
        )

            brand = ai_result.get("brand", "не определено")

    product_type = ai_result.get("product_type", "не определено")

    color = ai_result.get("color", "не определено")

    gender = ai_result.get("gender", "не определено")

    sizes = ai_result.get("sizes", "не определено")

    material = ai_result.get("material", "не определено")

    minimum_price = purchase_price + 1000

    recommended_price = ai_result.get ( 
    "recommended_price",
    purchase_price + 1500
    )

    expected_profit = recommended_price - purchase_price

    st.divider()
    st.header("Готовая карточка объявления")

    st.subheader("Что определил AVELON")

    st.write(f"Бренд: {brand}")
    st.write(f"Тип товара: {product_type}")
    st.write(f"Цвет: {color}")
    st.write(f"Пол: {gender}")
    st.write(f"Размеры: {sizes}")
    st.write(f"Материал: {material}")

    st.divider()

    st.subheader("Заголовок")

    title = ai_result.get(
    "title",
    f"{brand} {gender} {color} {product_type}"
)

    title = title[:50]

    st.write(title)
    st.caption(f"{len(title)} / 50 символов")
    
    st.subheader("Описание")

    description = ai_result.get(
    "description",
    f"""
🔥 {brand} — {gender} {color} {product_type}.

📏 Размеры: {sizes}
🎨 Цвет: {color}
👕 Тип: {product_type}
🧵 Материал: {material}
📦 Доставка по всей России.

{extra_info if extra_info.strip() else ""}

Есть вопросы по размерам или нужны дополнительные фото? Пишите или звоните прямо сейчас.
"""
)
    st.write(description)

    st.subheader("Действия")

    col1, col2, col3 = st.columns(3, gap="small")

    with col1:
        st.button(
            "Скопировать заголовок",
            use_container_width=True
        )

    with col2:
        st.button(
            "Скопировать описание",
            use_container_width=True
        )

    with col3:
        st.button(
            "Скопировать всё",
            use_container_width=True
        )

    col4, col5 = st.columns(2, gap="small")

    with col4:
        st.button(
            "Сохранить товар",
            use_container_width=True
        )

    with col5:
        st.button(
            "Перегенерировать",
            use_container_width=True
        )

    st.divider()

    st.subheader("Цена")
    st.write(f"Закупочная цена: {purchase_price:,.0f} ₽")
    st.write(f"Минимальная цена: {minimum_price:,.0f} ₽")
    st.write(f"Рекомендуемая цена: {recommended_price:,.0f} ₽")
    st.write(f"Ожидаемая прибыль: {expected_profit:,.0f} ₽")

    city = ai_result.get("city", "не определено")
    competition = ai_result.get("competition", "не определено")
    sale_probability = ai_result.get("sale_probability", "не определено")
    sale_time = ai_result.get("sale_time", "не определено")

    st.subheader("Аналитика")
    st.write(f"Рекомендуемый город: {city}")
    st.write(f"Конкуренция: {competition}")
    st.write(f"Вероятность продажи: {sale_probability}")
    st.write(f"Ожидаемый срок продажи: {sale_time}")

    photo_recommendations = ai_result.get(
        "photo_recommendations",
        "Рекомендации не определены"
    )

    st.subheader("Фотографии")

    if photos:
        st.write(f"Загружено фотографий: {len(photos)}")
        st.write(f"Рекомендации AVELON: {photo_recommendations}")
    else:
        st.write("Фотографии пока не загружены")