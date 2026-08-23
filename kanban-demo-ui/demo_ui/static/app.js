(() => {
  "use strict";

  function boardData() {
    const el = document.getElementById("board-data");
    return el ? JSON.parse(el.textContent) : { boardId: null, cards: {} };
  }

  function showToast(message, kind = "error") {
    const toast = document.getElementById("toast");
    if (!toast) return;
    toast.textContent = message;
    toast.dataset.kind = kind;
    toast.classList.add("show");
    window.setTimeout(() => toast.classList.remove("show"), 3600);
  }

  function openDialog(id) {
    const dialog = document.getElementById(id);
    if (dialog && !dialog.open) dialog.showModal();
  }

  function closeDialog(dialog) {
    if (dialog?.open) dialog.close();
  }

  document.addEventListener("click", (event) => {
    const open = event.target.closest("[data-open-dialog]");
    if (open) {
      openDialog(open.dataset.openDialog);
      return;
    }

    const close = event.target.closest("[data-close-dialog]");
    if (close) {
      closeDialog(close.closest("dialog"));
      return;
    }
  });

  document.querySelectorAll("dialog").forEach((dialog) => {
    dialog.addEventListener("click", (event) => {
      if (event.target === dialog) closeDialog(dialog);
    });
  });

  const board = boardData();

  // New card.
  document.querySelectorAll("[data-new-card]").forEach((button) => {
    button.addEventListener("click", () => {
      const firstColumn = document.querySelector(".column");
      const columnId = button.dataset.columnId || firstColumn?.dataset.columnId || "";

      document.getElementById("card-dialog-eyebrow").textContent = "New card";
      document.getElementById("card-dialog-title").textContent = "Add card";
      document.getElementById("card-form").action = `/boards/${board.boardId}/cards`;
      document.getElementById("card-column-id").value = columnId;
      document.getElementById("card-title").value = "";
      document.getElementById("card-description").value = "";
      document.getElementById("card-assignees").value = "";
      document.getElementById("card-size").value = "";
      document.getElementById("card-archived").checked = false;
      document.getElementById("archived-row").hidden = true;
      document.getElementById("dependency-section").hidden = true;
      document.getElementById("delete-card-button").hidden = true;

      openDialog("card-dialog");
      document.getElementById("card-title").focus();
    });
  });

  // Edit card.
  document.querySelectorAll("[data-card]").forEach((cardEl) => {
    const open = () => {
      const id = cardEl.dataset.cardId;
      const data = board.cards[id];

      document.getElementById("card-dialog-eyebrow").textContent = "Card";
      document.getElementById("card-dialog-title").textContent = "Edit card";
      document.getElementById("card-form").action =
        `/boards/${board.boardId}/cards/${id}`;
      document.getElementById("card-title").value = cardEl.dataset.title || "";
      document.getElementById("card-description").value =
        cardEl.dataset.description || "";
      document.getElementById("card-assignees").value =
        cardEl.dataset.assignees || "";
      document.getElementById("card-size").value = cardEl.dataset.size || "";
      document.getElementById("card-archived").checked =
        cardEl.dataset.archived === "true";
      document.getElementById("archived-row").hidden = false;
      document.getElementById("dependency-section").hidden = false;
      document.getElementById("delete-card-button").hidden = false;

      const select = document.getElementById("blocking-card-select");
      Array.from(select.options).forEach((option) => {
        option.hidden = option.value === id;
      });
      select.value = "";

      document.getElementById("blocked-by-list").innerHTML =
        (data?.blockedBy || []).map((blockerId) => {
          const blocker = board.cards[blockerId];
          const title = blocker?.title || blockerId.slice(0, 8);
          return `
            <div class="dependency-row">
              <span>Blocked by <strong>${escapeHtml(title)}</strong></span>
              <button type="button" class="text-button" data-unblock="${blockerId}">
                remove
              </button>
            </div>`;
        }).join("") || `<span class="muted">No blockers</span>`;

      document.getElementById("delete-card-form").action =
        `/boards/${board.boardId}/cards/${id}/delete`;
      document.getElementById("block-card-form").action =
        `/boards/${board.boardId}/cards/${id}/block`;
      document.getElementById("unblock-card-form").action =
        `/boards/${board.boardId}/cards/${id}/unblock`;

      openDialog("card-dialog");
    };

    cardEl.addEventListener("click", (event) => {
      if (!event.target.closest(".drag-handle")) open();
    });
    cardEl.addEventListener("keydown", (event) => {
      if (event.key === "Enter" || event.key === " ") {
        event.preventDefault();
        open();
      }
    });
  });

  document.getElementById("delete-card-button")?.addEventListener("click", () => {
    if (window.confirm("Delete this card?")) {
      document.getElementById("delete-card-form").submit();
    }
  });

  document.getElementById("add-blocker-button")?.addEventListener("click", () => {
    const select = document.getElementById("blocking-card-select");
    if (!select.value) {
      showToast("Choose a card first.");
      return;
    }
    document.getElementById("block-card-id").value = select.value;
    document.getElementById("block-card-form").submit();
  });

  document.getElementById("blocked-by-list")?.addEventListener("click", (event) => {
    const button = event.target.closest("[data-unblock]");
    if (!button) return;
    document.getElementById("unblock-card-id").value = button.dataset.unblock;
    document.getElementById("unblock-card-form").submit();
  });

  // Column settings.
  document.querySelectorAll("[data-column-settings]").forEach((button) => {
    button.addEventListener("click", () => {
      const id = button.dataset.columnId;
      document.getElementById("column-name").value = button.dataset.columnName || "";
      document.getElementById("column-wip").value = button.dataset.columnWip || "";
      document.getElementById("column-form").action =
        `/boards/${board.boardId}/columns/${id}`;
      document.getElementById("delete-column-form").action =
        `/boards/${board.boardId}/columns/${id}/delete`;
      openDialog("column-dialog");
    });
  });

  document.getElementById("delete-column-button")?.addEventListener("click", () => {
    if (window.confirm("Delete this column? It must be empty.")) {
      document.getElementById("delete-column-form").submit();
    }
  });

  // Native drag and drop.
  //
  // This deliberately avoids a third-party drag library. Each card is a native
  // draggable element and each card-list is a drop zone. The DOM is updated
  // optimistically, then the move is committed through KanbanFacade on the server.
  let draggedCard = null;
  let sourceList = null;
  let sourceNextSibling = null;

  function clearDragState() {
    document.body.classList.remove("is-dragging");
    document.querySelectorAll(".column.drop-target").forEach((column) => {
      column.classList.remove("drop-target");
    });
    document.querySelectorAll(".column.drag-source").forEach((column) => {
      column.classList.remove("drag-source");
    });
  }

  function restoreDraggedCard() {
    if (!draggedCard || !sourceList) return;
    if (sourceNextSibling && sourceNextSibling.parentElement === sourceList) {
      sourceList.insertBefore(draggedCard, sourceNextSibling);
    } else {
      sourceList.appendChild(draggedCard);
    }
  }

  function cardInsertionPoint(list, clientY) {
    const cards = Array.from(list.querySelectorAll("[data-card]"))
      .filter((card) => card !== draggedCard);

    for (const card of cards) {
      const box = card.getBoundingClientRect();
      if (clientY < box.top + box.height / 2) {
        return card;
      }
    }
    return null;
  }

  document.querySelectorAll("[data-card]").forEach((card) => {
    card.addEventListener("dragstart", (event) => {
      draggedCard = card;
      sourceList = card.closest(".card-list");
      sourceNextSibling = card.nextElementSibling;

      document.body.classList.add("is-dragging");
      sourceList?.closest(".column")?.classList.add("drag-source");
      card.classList.add("card-dragging");

      if (event.dataTransfer) {
        event.dataTransfer.effectAllowed = "move";
        event.dataTransfer.setData("text/plain", card.dataset.cardId || "");
      }
    });

    card.addEventListener("dragend", () => {
      card.classList.remove("card-dragging");
      clearDragState();
      draggedCard = null;
      sourceList = null;
      sourceNextSibling = null;
    });
  });

  document.querySelectorAll(".card-list").forEach((list) => {
    list.addEventListener("dragenter", (event) => {
      if (!draggedCard) return;
      event.preventDefault();
      document.querySelectorAll(".column.drop-target").forEach((column) => {
        column.classList.remove("drop-target");
      });
      list.closest(".column")?.classList.add("drop-target");
    });

    list.addEventListener("dragover", (event) => {
      if (!draggedCard) return;
      event.preventDefault();
      if (event.dataTransfer) {
        event.dataTransfer.dropEffect = "move";
      }

      const before = cardInsertionPoint(list, event.clientY);
      if (before) {
        list.insertBefore(draggedCard, before);
      } else {
        list.appendChild(draggedCard);
      }
    });

    list.addEventListener("drop", async (event) => {
      if (!draggedCard) return;
      event.preventDefault();

      const card = draggedCard;
      const cardId = card.dataset.cardId;
      const columnId = list.dataset.columnId;
      const cards = Array.from(list.querySelectorAll("[data-card]"));
      const position = cards.indexOf(card);

      clearDragState();

      const body = new URLSearchParams({
        to_column_id: columnId,
        position: String(position),
      });

      try {
        const response = await fetch(
          `/boards/${board.boardId}/cards/${cardId}/move`,
          {
            method: "POST",
            headers: { "Content-Type": "application/x-www-form-urlencoded" },
            body,
          },
        );
        const result = await response.json();

        if (!response.ok || !result.ok) {
          restoreDraggedCard();
          showToast(result.error || "Move rejected.");
          return;
        }

        showToast("Card moved", "success");
        htmx.trigger("#event-list", "refresh");

        // Refresh derived UI such as WIP counters after the server commit.
        window.setTimeout(() => window.location.reload(), 180);
      } catch (_error) {
        restoreDraggedCard();
        showToast("Could not save the move.");
      }
    });
  });

  function escapeHtml(value) {
    return String(value)
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;")
      .replaceAll("'", "&#039;");
  }
})();
