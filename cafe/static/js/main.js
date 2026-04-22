window.addEventListener('DOMContentLoaded', function() {
    var burger = document.querySelector('.burger');
    var nav = document.querySelector('.main-nav');
    var overlay = document.getElementById('menuOverlay');
    if (burger) burger.classList.remove('open');
    if (nav) nav.classList.remove('open');
    if (overlay) overlay.classList.remove('active');

    function closeMenu() {
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
            link.addEventListener('click', function() {
                closeMenu();
            });
        });
        if (overlay) {
            overlay.addEventListener('click', function() {
                closeMenu();
            });
        }
        document.addEventListener('click', function(e) {
            if (nav.classList.contains('open')) {
                if (!nav.contains(e.target) && !burger.contains(e.target)) {
                    closeMenu();
                }
            }
        });
    }
});


document.addEventListener('DOMContentLoaded', function() {
    document.querySelectorAll('.add-to-cart-btn').forEach(function(btn) {
        btn.addEventListener('click', function(e) {
            e.preventDefault();
            var productId = this.getAttribute('data-id');
            fetch('/cart/add/' + productId + '/', {
                method: 'POST',
                headers: {
                    'X-CSRFToken': getCookie('csrftoken'),
                    'X-Requested-With': 'XMLHttpRequest',
                },
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    updateCartCount(data.cart_items_count);
                    showToast('Товар добавлен в корзину!');
                }
            });
        });
    });
});

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

function getCookie(name) {
    let cookieValue = null;
    if (document.cookie && document.cookie !== '') {
        const cookies = document.cookie.split(';');
        for (let i = 0; i < cookies.length; i++) {
            const cookie = cookies[i].trim();
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
        var link = e.target.closest('.product-link');
        if (link && link.dataset.id) {
            e.preventDefault();
            openProductModal(link.dataset.id);
        }
        if (e.target.classList.contains('modal-product-overlay') || e.target.id === 'modalProductClose') {
            closeProductModal();
        }
    });
});

function openProductModal(productId) {
    fetch('/product/' + productId + '/modal/')
        .then(r => r.json())
        .then(data => {
            var modal = document.getElementById('modalProduct');
            var content = document.getElementById('modalProductContent');
            content.innerHTML = data.html;
            modal.style.display = 'flex';
            setTimeout(function() { modal.classList.add('active'); }, 10);
            content.querySelectorAll('.add-to-cart-btn').forEach(function(btn) {
                btn.addEventListener('click', function(e) {
                    e.preventDefault();
                    var productId = this.getAttribute('data-id');
                    fetch('/cart/add/' + productId + '/', {
                        method: 'POST',
                        headers: {
                            'X-CSRFToken': getCookie('csrftoken'),
                            'X-Requested-With': 'XMLHttpRequest',
                        },
                    })
                    .then(response => response.json())
                    .then(data => {
                        if (data.success) {
                            updateCartCount(data.cart_items_count);
                            showToast('Товар добавлен в корзину!');
                        }
                    });
                });
            });
        });
}

function closeProductModal() {
    var modal = document.getElementById('modalProduct');
    modal.classList.remove('active');
    setTimeout(function() { modal.style.display = 'none'; }, 200);
}

document.addEventListener('DOMContentLoaded', function() {
    var orderBtn = document.getElementById('openOrderModal');
    if (orderBtn) {
        orderBtn.addEventListener('click', function(e) {
            e.preventDefault();
            fetch('/order/modal/')
                .then(r => r.json())
                .then(data => {
                    var modal = document.getElementById('modalOrder');
                    var content = document.getElementById('modalOrderContent');
                    content.innerHTML = data.html;
                    modal.style.display = 'flex';
                    setTimeout(function() { modal.classList.add('active'); }, 10);
                    var closeBtn = document.getElementById('modalOrderClose');
                    if (closeBtn) {
                        closeBtn.onclick = closeOrderModal;
                    }
                    document.querySelector('.modal-order-overlay').onclick = closeOrderModal;
                    var form = document.getElementById('orderForm');
                    if (form) {
                        form.onsubmit = function(ev) {
                            ev.preventDefault();
                            var formData = new FormData(form);
                            fetch('/order/create/', {
                                method: 'POST',
                                headers: {
                                    'X-CSRFToken': getCookie('csrftoken'),
                                    'X-Requested-With': 'XMLHttpRequest',
                                },
                                body: formData
                            })
                            .then(r => r.json())
                            .then(data => {
                                if (data.success) {
                                    closeOrderModal();
                                    showToast('Заказ успешно оформлен!');
                                    setTimeout(function(){ window.location.reload(); }, 1200);
                                } else if (data.errors) {
                                    alert('Ошибка: ' + data.errors.join('\n'));
                                }
                            });
                        }
                    }
                });
        });
    }
});

function closeOrderModal() {
    var modal = document.getElementById('modalOrder');
    modal.classList.remove('active');
    setTimeout(function() { modal.style.display = 'none'; }, 200);
} 