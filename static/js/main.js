/**
 * main.js
 * 前端互動邏輯：
 * 1. 新增訂單頁面 (即時多選計算小計與總金額)
 * 2. 訂單列表頁面 (即時非同步切換訂單狀態)
 */

document.addEventListener("DOMContentLoaded", function () {
  // 1. 新增訂單：多選商品與即時計算小計 / 總金額
  const orderNewForm = document.getElementById("orderNewForm");
  if (orderNewForm) {
    const productCheckboxes = document.querySelectorAll(".product-select-chk");
    const summaryItemCount = document.getElementById("summaryItemCount");
    const summaryTotalQty = document.getElementById("summaryTotalQty");
    const summaryTotalAmount = document.getElementById("summaryTotalAmount");
    const submitBtn = document.getElementById("submitOrderBtn");

    function calculateOrderTotals() {
      let selectedCount = 0;
      let totalQty = 0;
      let grandTotal = 0;

      productCheckboxes.forEach((chk) => {
        const pid = chk.value;
        const row = document.getElementById(`row_${pid}`);
        const qtyInput = document.getElementById(`qty_${pid}`);
        const price = parseFloat(chk.dataset.price || 0);
        const subtotalSpan = document.getElementById(`subtotal_${pid}`);

        if (chk.checked) {
          selectedCount += 1;
          qtyInput.disabled = false;
          let qty = parseInt(qtyInput.value || 1, 10);
          if (qty < 1) {
            qty = 1;
            qtyInput.value = 1;
          }
          const subtotal = price * qty;
          totalQty += qty;
          grandTotal += subtotal;

          if (subtotalSpan) {
            subtotalSpan.textContent = subtotal.toLocaleString("zh-TW");
          }
          if (row) {
            row.classList.add("table-primary");
          }
        } else {
          qtyInput.disabled = true;
          if (subtotalSpan) {
            subtotalSpan.textContent = "0";
          }
          if (row) {
            row.classList.remove("table-primary");
          }
        }
      });

      if (summaryItemCount) summaryItemCount.textContent = selectedCount;
      if (summaryTotalQty) summaryTotalQty.textContent = totalQty;
      if (summaryTotalAmount) summaryTotalAmount.textContent = grandTotal.toLocaleString("zh-TW");

      // 若未勾選任何商品則禁用送出按鈕
      if (submitBtn) {
        submitBtn.disabled = selectedCount === 0;
      }
    }

    productCheckboxes.forEach((chk) => {
      chk.addEventListener("change", calculateOrderTotals);
    });

    const qtyInputs = document.querySelectorAll(".product-qty-input");
    qtyInputs.forEach((input) => {
      input.addEventListener("input", calculateOrderTotals);
      input.addEventListener("change", calculateOrderTotals);
    });

    // 初始計算一次
    calculateOrderTotals();
  }

  // 2. 訂單列表：即時直接切換訂單狀態 (AJAX)
  const statusSelects = document.querySelectorAll(".ajax-status-select");
  statusSelects.forEach((select) => {
    select.addEventListener("change", function () {
      const orderId = this.dataset.orderId;
      const newStatus = this.value;
      const originalStatus = this.dataset.currentStatus;

      // 提示切換中
      this.disabled = true;

      fetch(`/orders/${orderId}/status`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-Requested-With": "XMLHttpRequest",
        },
        body: JSON.stringify({ status: newStatus }),
      })
        .then((res) => res.json())
        .then((data) => {
          this.disabled = false;
          if (data.success) {
            this.dataset.currentStatus = newStatus;
            showQuickToast(`訂單 [${orderId}] 狀態已更新為「${newStatus}」`, "success");
            updateSelectClass(this, newStatus);
          } else {
            alert("更新狀態失敗：" + (data.error || "未知錯誤"));
            this.value = originalStatus;
          }
        })
        .catch((err) => {
          this.disabled = false;
          alert("網路錯誤或連線中斷：" + err);
          this.value = originalStatus;
        });
    });
  });

  function updateSelectClass(selectElem, status) {
    selectElem.classList.remove(
      "border-warning",
      "border-info",
      "border-success",
      "border-secondary"
    );
    if (status === "處理中") selectElem.classList.add("border-warning");
    else if (status === "已出貨") selectElem.classList.add("border-info");
    else if (status === "已完成") selectElem.classList.add("border-success");
    else if (status === "已取消") selectElem.classList.add("border-secondary");
  }

  function showQuickToast(message, type = "success") {
    let container = document.getElementById("toastContainer");
    if (!container) {
      container = document.createElement("div");
      container.id = "toastContainer";
      container.className = "toast-container position-fixed bottom-0 end-0 p-3";
      container.style.zIndex = "1090";
      document.body.appendChild(container);
    }

    const toastEl = document.createElement("div");
    toastEl.className = `toast align-items-center text-bg-${type} border-0 show shadow-lg`;
    toastEl.setAttribute("role", "alert");
    toastEl.innerHTML = `
      <div class="d-flex">
        <div class="toast-body">
          <i class="bi bi-check-circle-fill me-2"></i> ${message}
        </div>
        <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast"></button>
      </div>
    `;
    container.appendChild(toastEl);
    setTimeout(() => {
      toastEl.classList.remove("show");
      setTimeout(() => toastEl.remove(), 300);
    }, 3000);
  }
});
