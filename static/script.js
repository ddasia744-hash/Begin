const regionInput = document.getElementById("region-input");
const suggestionsEl = document.getElementById("region-suggestions");
const searchBtn = document.getElementById("search-btn");
const selectedRegionEl = document.getElementById("selected-region");
const statusEl = document.getElementById("status-msg");
const resultsEl = document.getElementById("results");
const realEstateTypeEl = document.getElementById("real-estate-type");
const tradeTypeEl = document.getElementById("trade-type");

let selectedRegion = null;
let debounceTimer = null;
let activeIndex = -1;

function debounce(fn, delay) {
  return (...args) => {
    clearTimeout(debounceTimer);
    debounceTimer = setTimeout(() => fn(...args), delay);
  };
}

async function fetchSuggestions(query) {
  if (!query.trim()) {
    hideSuggestions();
    return;
  }
  const res = await fetch(`/api/regions?q=${encodeURIComponent(query)}`);
  const data = await res.json();
  renderSuggestions(data);
}

function renderSuggestions(items) {
  suggestionsEl.innerHTML = "";
  activeIndex = -1;

  if (!items.length) {
    hideSuggestions();
    return;
  }

  items.forEach((item) => {
    const li = document.createElement("li");
    li.textContent = item.full_name;
    const codeSpan = document.createElement("span");
    codeSpan.className = "region-code";
    codeSpan.textContent = item.code;
    li.appendChild(codeSpan);
    li.addEventListener("click", () => selectRegion(item));
    suggestionsEl.appendChild(li);
  });

  suggestionsEl.classList.remove("hidden");
}

function hideSuggestions() {
  suggestionsEl.classList.add("hidden");
  suggestionsEl.innerHTML = "";
}

function selectRegion(item) {
  selectedRegion = item;
  regionInput.value = item.full_name;
  selectedRegionEl.textContent = `선택된 지역: ${item.full_name} (법정동코드 ${item.code})`;
  hideSuggestions();
  searchBtn.disabled = false;
}

regionInput.addEventListener("input", () => {
  selectedRegion = null;
  searchBtn.disabled = true;
  debounce(fetchSuggestions, 200)(regionInput.value);
});

regionInput.addEventListener("keydown", (e) => {
  const items = Array.from(suggestionsEl.children);
  if (!items.length) return;

  if (e.key === "ArrowDown") {
    e.preventDefault();
    activeIndex = Math.min(activeIndex + 1, items.length - 1);
    updateActive(items);
  } else if (e.key === "ArrowUp") {
    e.preventDefault();
    activeIndex = Math.max(activeIndex - 1, 0);
    updateActive(items);
  } else if (e.key === "Enter" && activeIndex >= 0) {
    e.preventDefault();
    items[activeIndex].click();
  } else if (e.key === "Escape") {
    hideSuggestions();
  }
});

function updateActive(items) {
  items.forEach((el, idx) => el.classList.toggle("active", idx === activeIndex));
  items[activeIndex]?.scrollIntoView({ block: "nearest" });
}

document.addEventListener("click", (e) => {
  if (!e.target.closest(".autocomplete")) hideSuggestions();
});

searchBtn.addEventListener("click", async () => {
  if (!selectedRegion) return;

  statusEl.textContent = "";
  resultsEl.innerHTML = "";
  searchBtn.disabled = true;
  searchBtn.textContent = "조회 중...";

  const params = new URLSearchParams({
    cortarNo: selectedRegion.code,
    realEstateType: realEstateTypeEl.value,
    tradeType: tradeTypeEl.value,
  });

  try {
    const res = await fetch(`/api/listings?${params}`);
    const data = await res.json();

    if (!res.ok) {
      statusEl.textContent = `${data.error || "조회에 실패했습니다."} ${data.detail ? `(${data.detail})` : ""}`;
      return;
    }

    renderArticles(data.articles);
  } catch (err) {
    statusEl.textContent = `요청 중 오류가 발생했습니다: ${err.message}`;
  } finally {
    searchBtn.disabled = false;
    searchBtn.textContent = "매물 조회";
  }
});

function renderArticles(articles) {
  if (!articles.length) {
    resultsEl.innerHTML = '<p class="status-msg" style="color:#6b7280">조회된 매물이 없습니다.</p>';
    return;
  }

  resultsEl.innerHTML = articles
    .map(
      (a) => `
    <article class="article-card">
      <div class="row1">
        <span class="name">${a.name ?? "-"}</span>
        <span class="price">${a.tradeType ?? ""} ${a.price ?? ""}${a.rentPrice ? " / " + a.rentPrice : ""}</span>
      </div>
      <div class="meta">${a.type ?? ""} · ${a.area ?? "-"}㎡ · ${a.floor ?? "-"} · ${a.direction ?? "-"}</div>
      ${a.description ? `<div class="desc">${a.description}</div>` : ""}
      <div class="realtor">${a.realtor ?? ""} ${a.confirmDate ? "· 확인일 " + a.confirmDate : ""}</div>
    </article>
  `
    )
    .join("");
}
