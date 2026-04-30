window.addEventListener('DOMContentLoaded', function() {
    var burger = document.querySelector('.burger');
    var nav = document.querySelector('.main-nav');
    var overlay = document.getElementById('menuOverlay');
    if (burger) burger.classList.remove('open');
    if (nav) nav.classList.remove('open');
    if (overlay) overlay.classList.remove('active');

    function closeMenu() {
        if (!nav || !burger) return;
        nav.classList.remove('open');
        burger.classList.remove('open');
        if (overlay) overlay.classList.remove('active');
    }

    if (burger && nav) {
        burger.addEventListener('click', function(e) {
            e.stopPropagation();
            nav.classList.toggle('open');
            burger.classList.toggle('open');
            if (overlay) overlay.classList.toggle('active');
        });
        nav.querySelectorAll('a').forEach(function(link) {
            link.addEventListener('click', closeMenu);
        });
        if (overlay) {
            overlay.addEventListener('click', closeMenu);
        }
        document.addEventListener('click', function(e) {
            if (nav.classList.contains('open') && !nav.contains(e.target) && !burger.contains(e.target)) {
                closeMenu();
            }
        });
    }
});

document.addEventListener('DOMContentLoaded', function() {
    document.querySelectorAll('.add-to-cart-btn').forEach(function(btn) {
        btn.addEventListener('click', function(e) {
            e.preventDefault();
            addProductToCart(this.getAttribute('data-id'));
        });
    });
});

function addProductToCart(productId) {
    if (!productId) return;

    fetch('/cart/add/' + productId + '/', {
        method: 'POST',
        headers: {
            'X-CSRFToken': getCookie('csrftoken'),
            'X-Requested-With': 'XMLHttpRequest',
        },
    })
    .then(function(response) {
        if (!response.ok) throw new Error('cart-add-failed');
        return response.json();
    })
    .then(function(data) {
        if (data.success) {
            updateCartCount(data.cart_items_count);
            showToast('Товар добавлен в корзину!');
        }
    })
    .catch(function() {
        showToast('Не удалось добавить товар. Попробуйте позже.');
    });
}

function updateCartCount(count) {
    var cartCount = document.querySelector('.cart-count');
    if (!cartCount) {
        var cartEllipse = document.querySelector('.cart-ellipse');
        if (cartEllipse) {
            cartCount = document.createElement('span');
            cartCount.className = 'cart-count';
            cartEllipse.appendChild(cartCount);
        }
    }
    if (cartCount) {
        cartCount.textContent = count;
        cartCount.style.display = count > 0 ? 'flex' : 'none';
    }
}

function showToast(msg) {
    var toast = document.createElement('div');
    toast.className = 'custom-toast';
    toast.textContent = msg;
    document.body.appendChild(toast);
    setTimeout(function() {
        toast.classList.add('show');
    }, 10);
    setTimeout(function() {
        toast.classList.remove('show');
        setTimeout(function() { toast.remove(); }, 300);
    }, 1800);
}

function setSubmitState(button, isLoading, loadingText) {
    if (!button) return;
    if (isLoading) {
        button.dataset.originalText = button.textContent;
        button.textContent = loadingText || 'Отправляем...';
        button.disabled = true;
        button.classList.add('is-loading');
    } else {
        button.textContent = button.dataset.originalText || button.textContent;
        button.disabled = false;
        button.classList.remove('is-loading');
    }
}

function getCookie(name) {
    var cookieValue = null;
    if (document.cookie && document.cookie !== '') {
        var cookies = document.cookie.split(';');
        for (var i = 0; i < cookies.length; i++) {
            var cookie = cookies[i].trim();
            if (cookie.substring(0, name.length + 1) === (name + '=')) {
                cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                break;
            }
        }
    }
    return cookieValue;
}

document.addEventListener('DOMContentLoaded', function() {
    document.body.addEventListener('click', function(e) {
        if (e.target.closest('.add-to-cart-btn')) {
            return;
        }
        if (e.target.closest('.product-fav-toggle') || e.target.classList.contains('product-fav-toggle')) {
            return; // Prevent clicking on fav icon to open modal
        }
        var link = e.target.closest('.product-link');
        if (link && link.dataset.id) {
            e.preventDefault();
            openProductModal(link.dataset.id);
        }
        if (e.target.classList.contains('modal-product-overlay') || e.target.closest('#modalProductClose')) {
            closeProductModal();
        }
    });

    document.body.addEventListener('keydown', function(e) {
        var link = e.target.closest('.product-link');
        if (!link || !link.dataset.id) return;
        if (e.key === 'Enter' || e.key === ' ') {
            e.preventDefault();
            openProductModal(link.dataset.id);
        }
    });
});

document.addEventListener('keydown', function(e) {
    if (e.key !== 'Escape') return;
    closeProductModal();
    closeOrderModal();
});

function openProductModal(productId) {
    fetch('/product/' + productId + '/modal/')
        .then(function(response) {
            if (!response.ok) throw new Error('product-modal-failed');
            return response.json();
        })
        .then(function(data) {
            var modal = document.getElementById('modalProduct');
            var content = document.getElementById('modalProductContent');
            if (!modal || !content) return;

            content.innerHTML = data.html;
            modal.style.display = 'flex';
            setTimeout(function() { modal.classList.add('active'); }, 10);
            content.querySelectorAll('.add-to-cart-btn').forEach(function(btn) {
                btn.addEventListener('click', function(e) {
                    e.preventDefault();
                    addProductToCart(this.getAttribute('data-id'));
                });
            });
        })
        .catch(function() {
            showToast('Не удалось открыть товар. Попробуйте позже.');
        });
}

function closeProductModal() {
    var modal = document.getElementById('modalProduct');
    if (!modal) return;
    modal.classList.remove('active');
    setTimeout(function() { modal.style.display = 'none'; }, 200);
}

document.addEventListener('DOMContentLoaded', function() {
    var orderBtn = document.getElementById('openOrderModal');
    if (orderBtn) {
        orderBtn.addEventListener('click', function(e) {
            e.preventDefault();
            fetch('/order/modal/')
                .then(function(response) {
                    if (!response.ok) throw new Error('order-modal-failed');
                    return response.json();
                })
                .then(function(data) {
                    var modal = document.getElementById('modalOrder');
                    var content = document.getElementById('modalOrderContent');
                    if (!modal || !content) return;

                    content.innerHTML = data.html;
                    modal.style.display = 'flex';
                    setTimeout(function() { modal.classList.add('active'); }, 10);

                    var closeBtn = document.getElementById('modalOrderClose');
                    if (closeBtn) {
                        closeBtn.onclick = closeOrderModal;
                    }

                    var overlay = document.querySelector('.modal-order-overlay');
                    if (overlay) {
                        overlay.onclick = closeOrderModal;
                    }

                    setupOrderTotals();

                    var form = document.getElementById('orderForm');
                    if (form) {
                        form.onsubmit = function(ev) {
                            ev.preventDefault();
                            var submitBtn = form.querySelector('.order-modal-submit');
                            setSubmitState(submitBtn, true, 'Оформляем...');
                            var formData = new FormData(form);
                            fetch('/order/create/', {
                                method: 'POST',
                                headers: {
                                    'X-CSRFToken': getCookie('csrftoken'),
                                    'X-Requested-With': 'XMLHttpRequest',
                                },
                                body: formData
                            })
                            .then(function(response) {
                                return response.json().then(function(data) {
                                    if (!response.ok) throw data;
                                    return data;
                                });
                            })
                            .then(function(data) {
                                if (data.success) {
                                    closeOrderModal();
                                    showToast('Заказ успешно оформлен!');
                                    setTimeout(function() {
                                        window.location.href = data.order_url || '/cart/';
                                    }, 650);
                                }
                            })
                            .catch(function(data) {
                                var errors = data && data.errors ? data.errors : ['Не удалось оформить заказ. Попробуйте позже.'];
                                showToast('Ошибка: ' + errors.join(' '));
                                setSubmitState(submitBtn, false);
                            });
                        };
                    }
                })
                .catch(function() {
                    showToast('Не удалось открыть оформление заказа.');
                });
        });
    }
});

function setupOrderTotals() {
    var deliveryType = document.getElementById('deliveryType');
    var address = document.getElementById('deliveryAddress');
    var itemsPriceEl = document.getElementById('orderItemsPrice');
    var deliveryPriceEl = document.getElementById('orderDeliveryPrice');
    var totalPriceEl = document.getElementById('orderTotalPrice');
    if (!deliveryType || !itemsPriceEl || !deliveryPriceEl || !totalPriceEl) return;

    function parseMoney(value) {
        var normalized = String(value || '0')
            .replace(/\s/g, '')
            .replace(',', '.')
            .replace(/[^\d.-]/g, '');
        var parsed = Number(normalized);
        return Number.isFinite(parsed) ? parsed : 0;
    }

    var itemsPrice = parseMoney(itemsPriceEl.dataset.value || itemsPriceEl.textContent);
    var moneyFormatter = new Intl.NumberFormat('ru-RU', {
        minimumFractionDigits: 2,
        maximumFractionDigits: 2
    });

    function formatMoney(value) {
        return moneyFormatter.format(value);
    }

    function refreshTotals() {
        var isDelivery = deliveryType.value === 'delivery';
        var deliveryPrice = isDelivery ? 100 : 0;
        deliveryPriceEl.textContent = formatMoney(deliveryPrice);
        totalPriceEl.textContent = formatMoney(itemsPrice + deliveryPrice);
        if (address) {
            address.required = isDelivery;
            var addressBlock = document.getElementById('addressBlock');
            if (addressBlock) {
                addressBlock.style.display = isDelivery ? 'flex' : 'none';
            }
        }
    }

    deliveryType.addEventListener('change', refreshTotals);
    refreshTotals();
}

function closeOrderModal() {
    var modal = document.getElementById('modalOrder');
    if (!modal) return;
    modal.classList.remove('active');
    setTimeout(function() { modal.style.display = 'none'; }, 200);
}

document.addEventListener('DOMContentLoaded', function() {
    var favToggles = document.querySelectorAll('.product-fav-toggle');
    favToggles.forEach(function(toggle) {
        toggle.addEventListener('click', function(e) {
            e.stopPropagation();
            var productId = this.dataset.id;
            var el = this;
            fetch('/favorite/toggle/' + productId + '/', {
                method: 'POST',
                headers: {
                    'X-CSRFToken': getCookie('csrftoken'),
                    'Content-Type': 'application/json'
                }
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    if (data.is_favorite) {
                        el.innerHTML = '<i class="fa-solid fa-heart"></i>';
                    } else {
                        el.innerHTML = '<i class="fa-regular fa-heart"></i>';
                        // If we are on favorites page, maybe remove the card
                        if (window.location.pathname.indexOf('favorites') !== -1) {
                            el.closest('.product-card').remove();
                            // Optional: show "empty" message if no cards left
                            if(document.querySelectorAll('.product-card').length === 0) {
                                window.location.reload();
                            }
                        }
                    }
                } else {
                    showToast('Ошибка при изменении избранного.');
                }
            })
            .catch(err => {
                console.error(err);
                showToast('Ошибка сети.');
            });
        });
    });
});
