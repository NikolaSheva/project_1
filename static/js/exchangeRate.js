function formatCurrency(value) {
    return new Intl.NumberFormat('ru-RU', {
        style: 'currency',
        currency: 'RUB',
        minimumFractionDigits: 2
    }).format(value);
}

function updateUsdRate() {
    fetch('https://open.er-api.com/v6/latest/USD')
        .then(response => {
            if (!response.ok) {
                throw new Error("HTTP error " + response.status);
            }
            return response.json();
        })
        .then(data => {
            const rate = data.rates.RUB;
            document.getElementById('live-usd-rate').textContent = `1 USD ≈ ${formatCurrency(rate)}`;
            document.getElementById('rate-update-time').textContent = `Обновлено: ${new Date().toLocaleString()}`;
        })
        .catch(error => {
            console.error("Ошибка загрузки курса валюты:", error);
            const rateElem = document.getElementById('live-usd-rate');
            if (rateElem) {
                rateElem.textContent = "Ошибка загрузки курса";
            }
        });
}

document.addEventListener('DOMContentLoaded', function () {
    updateUsdRate(); // при загрузке
    setInterval(updateUsdRate, 10 * 60 * 1000); // каждые 10 минут
});