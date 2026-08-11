print("AVELON Marketplace AI запущен")
import streamlit as st
from ai_client import generate_listing
import json
import os

SAVED_PRODUCTS_FILE = "saved_products.json"


def load_saved_products():
    if not os.path.exists(SAVED_PRODUCTS_FILE):
        return []

    try:
        with open(SAVED_PRODUCTS_FILE, "r", encoding="utf-8") as file:
            return json.load(file)
    except (json.JSONDecodeError, OSError):
        return []


def save_saved_products(products):
    with open(SAVED_PRODUCTS_FILE, "w", encoding="utf-8") as file:
        json.dump(
            products,
            file,
            ensure_ascii=False,
            indent=2
        )

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

if "listing_created" not in st.session_state:
    st.session_state["listing_created"] = False

if "saved_products" not in st.session_state:
    st.session_state["saved_products"] = load_saved_products()
    
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

    st.session_state["ai_result"] = ai_result
    st.session_state["supplier_text"] = supplier_text
    st.session_state["purchase_price"] = purchase_price
    st.session_state["extra_info"] = extra_info
    st.session_state["listing_created"] = True

if st.session_state.get("listing_created"):
    ai_result = st.session_state["ai_result"]
    supplier_text = st.session_state["supplier_text"]
    purchase_price = st.session_state["purchase_price"]
    extra_info = st.session_state["extra_info"]

    if st.session_state.get("opened_product"):
        st.success(
            f"Открыт сохранённый товар: "
            f"{st.session_state['opened_product']}"
        )
        st.session_state["opened_product"] = None

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
    formatted_description = description.replace("\n", "  \n")
    st.markdown(formatted_description)

    st.subheader("Действия")

    col1, col2, col3 = st.columns(3, gap="small")

    with col1:
        if st.button(
            "Скопировать заголовок",
            use_container_width=True
        ):
            st.session_state["copy_mode"] = "title"

    with col2:
        if st.button(
            "Скопировать описание",
            use_container_width=True
        ):
            st.session_state["copy_mode"] = "description"

    with col3:
        if st.button(
            "Скопировать всё",
            use_container_width=True
        ):
            st.session_state["copy_mode"] = "all"

    col4, col5 = st.columns(2, gap="small")

    with col4:
       if st.button(
        "Сохранить товар",
        use_container_width=True
    ):
        if "saved_products" not in st.session_state:
            st.session_state["saved_products"] = []

        saved_product = {
            "title": title,
            "description": description,
            "purchase_price": purchase_price,
            "recommended_price": recommended_price,
            "supplier_text": supplier_text,
            "extra_info": extra_info,
            "ai_result": ai_result,
        }

        st.session_state["saved_products"].append(saved_product)

        save_saved_products(
            st.session_state["saved_products"]
        )

        st.session_state["product_saved"] = True

    with col5:
        if st.button(
            "Перегенерировать",
            use_container_width=True
        ):
            with st.spinner("AVELON создаёт новый вариант..."):
                ai_result = generate_listing(
                    supplier_text=supplier_text,
                    purchase_price=purchase_price,
                    extra_info=extra_info,
                )

            st.session_state["ai_result"] = ai_result
            st.session_state["copy_mode"] = None
            st.session_state["product_saved"] = False

            st.rerun()

    if st.session_state.get("product_saved"):
        st.success("Товар сохранён.")

    copy_mode = st.session_state.get("copy_mode")

    if copy_mode == "title":
        st.caption("Нажми значок копирования справа:")
        st.code(title, language=None)

    elif copy_mode == "description":
        st.caption("Нажми значок копирования справа:")
        st.code(description.strip(), language=None)

    elif copy_mode == "all":
        copy_all_text = f"""{title}

{description.strip()}

Рекомендуемая цена: {recommended_price:,.0f} ₽
Город: {ai_result.get("city", "не определено")}
"""
        st.caption("Нажми значок копирования справа:")
        st.code(copy_all_text, language=None)

    st.divider()

    st.subheader("Цена")
    st.write(f"Закупочная цена: {purchase_price:,.0f} ₽")
    st.write(f"Минимальная цена: {minimum_price:,.0f} ₽")
    st.write(f"Рекомендуемая цена: {recommended_price:,.0f} ₽")
    st.write(f"Ожидаемая прибыль: {expected_profit:,.0f} ₽")

    city = ai_result.get("city", "не определено")
    city_reason = ai_result.get("city_reason", "Причина не определена")
    competition = ai_result.get("competition", "не определено")
    sale_probability = ai_result.get("sale_probability", "не определено")
    if isinstance(sale_probability, str):
        sale_probability = sale_probability.strip()
    sale_time = ai_result.get("sale_time", "не определено")

    st.subheader("Аналитика")
    st.write(f"Рекомендуемый город: {city}")
    st.caption(f"Почему: {city_reason}")
    st.write(f"Конкуренция: {competition}")
    st.write(f"Вероятность продажи: {sale_probability}")
    st.write(f"Ожидаемый срок продажи: {sale_time}")

    if "ai_result" in st.session_state:
        photo_recommendations = st.session_state["ai_result"].get(
        "photo_recommendations",
        "Рекомендации не определены"
    )

    st.subheader("Фотографии")

    if photos:
        st.write(f"Загружено фотографий: {len(photos)}")
        st.markdown("### Рекомендации AVELON по фото")

        recommendation_items = [
            item.strip()
            for item in photo_recommendations.replace("\n", " ").split(".")
            if item.strip()
        ]

        for index, item in enumerate(recommendation_items, start=1):
            st.write(f"{index}. {item}")

    else:
        st.write("Фотографии пока не загружены")

if st.session_state.get("saved_products"):
    st.divider()
    st.header("Сохранённые товары")

    for index, product in enumerate(
        st.session_state["saved_products"],
        start=1
    ):
        with st.expander(
            f"{index}. {product['title']}"
        ):
            st.write(
                f"Закупочная цена: "
                f"{product['purchase_price']:,.0f} ₽"
            )

            st.write(
                f"Рекомендуемая цена: "
                f"{product['recommended_price']:,.0f} ₽"
            )

            st.markdown("### Описание")

            st.markdown(
                product["description"].replace(
                    "\n",
                    "  \n"
                )
            )

            col_open, col_delete = st.columns(2)

            with col_open:
                if st.button(
                    "Открыть",
                    key=f"open_{index}",
                    use_container_width=True
                ):
                    st.session_state["ai_result"] = product["ai_result"]
                    st.session_state["supplier_text"] = product["supplier_text"]
                    st.session_state["purchase_price"] = product["purchase_price"]
                    st.session_state["extra_info"] = product["extra_info"]

                    st.session_state["listing_created"] = True
                    st.session_state["copy_mode"] = None
                    st.session_state["product_saved"] = False
                    st.session_state["opened_product"] = product["title"]

                    st.rerun()

            with col_delete:
                if st.button(
                    "Удалить",
                    key=f"delete_{index}",
                    use_container_width=True
                ):
                    del st.session_state["saved_products"][index - 1]

                    save_saved_products(
                        st.session_state["saved_products"]
                    )

                    st.rerun()