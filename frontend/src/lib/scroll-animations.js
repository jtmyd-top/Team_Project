/**
 * 滚动动画库
 * 基于滚动位置的动画效果
 */

class ScrollAnimations {
    constructor(options = {}) {
        this.options = {
            root: null,
            rootMargin: '0px',
            threshold: 0.1,
            animateClass: 'scroll-animate',
            animatedClass: 'animated',
            ...options
        };

        this.elements = [];
        this.observer = null;
        this.init();
    }

    init() {
        this.createObserver();
        this.observeElements();
        this.bindEvents();
    }

    createObserver() {
        this.observer = new IntersectionObserver((entries) => {
            entries.forEach(entry => {
                if (entry.isIntersecting) {
                    this.animateElement(entry.target);
                }
            });
        }, {
            root: this.options.root,
            rootMargin: this.options.rootMargin,
            threshold: this.options.threshold
        });
    }

    observeElements() {
        const elements = document.querySelectorAll(`.${this.options.animateClass}`);
        elements.forEach(element => {
            this.elements.push(element);
            this.observer.observe(element);
        });
    }

    animateElement(element) {
        // 添加动画类
        element.classList.add(this.options.animatedClass);

        // 根据data属性应用不同的动画
        const animationType = element.dataset.animation || 'fadeInUp';
        const delay = element.dataset.delay || 0;
        const duration = element.dataset.duration || 0.6;

        // 设置延迟和持续时间
        element.style.animationDelay = `${delay}s`;
        element.style.animationDuration = `${duration}s`;

        // 应用对应的动画
        this.applyAnimation(element, animationType);

        // 停止观察已动画的元素
        this.observer.unobserve(element);
    }

    applyAnimation(element, type) {
        const animations = {
            fadeInUp: 'fadeInUp 0.6s ease-out forwards',
            fadeInDown: 'fadeInDown 0.6s ease-out forwards',
            fadeInLeft: 'fadeInLeft 0.6s ease-out forwards',
            fadeInRight: 'fadeInRight 0.6s ease-out forwards',
            scaleIn: 'scaleIn 0.5s ease-out forwards',
            bounceIn: 'bounceIn 0.8s ease-out forwards',
            rotateIn: 'rotateIn 0.6s ease-out forwards',
            slideInLeft: 'slideInLeft 0.7s ease-out forwards',
            slideInRight: 'slideInRight 0.7s ease-out forwards',
            slideInUp: 'slideInUp 0.7s ease-out forwards',
            slideInDown: 'slideInDown 0.7s ease-out forwards'
        };

        element.style.animation = animations[type] || animations.fadeInUp;
    }

    bindEvents() {
        // 动态添加的元素也需要观察
        const observer = new MutationObserver((mutations) => {
            mutations.forEach((mutation) => {
                mutation.addedNodes.forEach((node) => {
                    if (node.nodeType === Node.ELEMENT_NODE) {
                        const newElements = node.querySelectorAll ?
                            node.querySelectorAll(`.${this.options.animateClass}`) : [];

                        newElements.forEach(element => {
                            this.elements.push(element);
                            this.observer.observe(element);
                        });

                        // 如果节点本身有动画类
                        if (node.classList && node.classList.contains(this.options.animateClass)) {
                            this.elements.push(node);
                            this.observer.observe(node);
                        }
                    }
                });
            });
        });

        observer.observe(document.body, {
            childList: true,
            subtree: true
        });
    }

    refresh() {
        // 重新扫描所有需要动画的元素
        this.elements.forEach(element => {
            this.observer.unobserve(element);
        });
        this.elements = [];
        this.observeElements();
    }

    destroy() {
        if (this.observer) {
            this.observer.disconnect();
        }
        this.elements = [];
    }
}

// 视差滚动效果
class ParallaxEffect {
    constructor(options = {}) {
        this.options = {
            speed: 0.5,
            elements: '[data-parallax]',
            ...options
        };

        this.elements = [];
        this.init();
    }

    init() {
        this.findElements();
        this.bindEvents();
    }

    findElements() {
        const elements = document.querySelectorAll(this.options.elements);
        elements.forEach(element => {
            const speed = parseFloat(element.dataset.speed) || this.options.speed;
            this.elements.push({
                element: element,
                speed: speed,
                initialY: 0
            });
        });
    }

    bindEvents() {
        let ticking = false;

        const updateParallax = () => {
            const scrollY = window.pageYOffset;

            this.elements.forEach(item => {
                if (item.initialY === 0) {
                    item.initialY = item.element.offsetTop;
                }

                const yPos = -(scrollY * item.speed);
                item.element.style.transform = `translateY(${yPos}px)`;
            });

            ticking = false;
        };

        const onScroll = () => {
            if (!ticking) {
                requestAnimationFrame(updateParallax);
                ticking = true;
            }
        };

        window.addEventListener('scroll', onScroll);
        window.addEventListener('resize', updateParallax);
    }
}

// 滚动进度指示器
class ScrollProgress {
    constructor(options = {}) {
        this.options = {
            container: document.body,
            height: '3px',
            color: '#667eea',
            position: 'top',
            ...options
        };

        this.progressBar = null;
        this.init();
    }

    init() {
        this.createProgressBar();
        this.bindEvents();
    }

    createProgressBar() {
        this.progressBar = document.createElement('div');
        this.progressBar.className = 'scroll-progress-bar';
        this.progressBar.style.cssText = `
            position: fixed;
            ${this.options.position}: 0;
            left: 0;
            width: 0%;
            height: ${this.options.height};
            background: ${this.options.color};
            z-index: 9999;
            transition: width 0.1s ease-out;
            pointer-events: none;
        `;

        this.options.container.appendChild(this.progressBar);
    }

    bindEvents() {
        let ticking = false;

        const updateProgress = () => {
            const scrollHeight = document.documentElement.scrollHeight - window.innerHeight;
            const scrollProgress = (window.pageYOffset / scrollHeight) * 100;

            this.progressBar.style.width = `${scrollProgress}%`;
            ticking = false;
        };

        const onScroll = () => {
            if (!ticking) {
                requestAnimationFrame(updateProgress);
                ticking = true;
            }
        };

        window.addEventListener('scroll', onScroll);
        window.addEventListener('resize', updateProgress);
    }
}

// 自动初始化
document.addEventListener('DOMContentLoaded', () => {
    // 初始化滚动动画
    if (typeof window.scrollAnimationsEnabled === 'undefined' || window.scrollAnimationsEnabled) {
        window.scrollAnimations = new ScrollAnimations();
    }

    // 初始化视差效果
    if (typeof window.parallaxEnabled === 'undefined' || window.parallaxEnabled) {
        window.parallaxEffect = new ParallaxEffect();
    }

    // 初始化滚动进度条
    if (typeof window.scrollProgressEnabled !== false) {
        window.scrollProgress = new ScrollProgress();
    }
});

// 页面加载动画
class PageLoader {
    constructor(options = {}) {
        this.options = {
            duration: 1000,
            minDuration: 500,
            fadeOutDuration: 500,
            ...options
        };

        this.loaderElement = null;
        this.startTime = null;
        this.init();
    }

    init() {
        this.createLoader();
        this.startLoading();
    }

    createLoader() {
        this.loaderElement = document.createElement('div');
        this.loaderElement.className = 'page-loader';
        this.loaderElement.innerHTML = `
            <div class="loader-content">
                <div class="loader-spinner"></div>
                <div class="loader-text">加载中...</div>
            </div>
        `;

        // 添加样式
        const style = document.createElement('style');
        style.textContent = `
            .page-loader {
                position: fixed;
                top: 0;
                left: 0;
                width: 100%;
                height: 100%;
                background: var(--bg-primary);
                display: flex;
                justify-content: center;
                align-items: center;
                z-index: 9999;
                transition: opacity ${this.options.fadeOutDuration}ms ease-out;
            }

            .loader-content {
                text-align: center;
            }

            .loader-spinner {
                width: 50px;
                height: 50px;
                margin: 0 auto 20px;
                border: 3px solid var(--border-color);
                border-top: 3px solid var(--primary-color);
                border-radius: 50%;
                animation: spin 1s linear infinite;
            }

            .loader-text {
                font-size: 16px;
                color: var(--text-secondary);
                font-weight: 500;
            }

            .page-loader.hide {
                opacity: 0;
                pointer-events: none;
            }
        `;
        document.head.appendChild(style);

        document.body.appendChild(this.loaderElement);
    }

    startLoading() {
        this.startTime = Date.now();
    }

    hide() {
        const elapsedTime = Date.now() - this.startTime;
        const remainingTime = Math.max(0, this.options.minDuration - elapsedTime);

        setTimeout(() => {
            this.loaderElement.classList.add('hide');

            setTimeout(() => {
                if (this.loaderElement.parentNode) {
                    this.loaderElement.parentNode.removeChild(this.loaderElement);
                }
            }, this.options.fadeOutDuration);
        }, remainingTime);
    }
}

// 页面加载时显示加载器
window.addEventListener('load', () => {
    // 隐藏页面加载器
    const pageLoader = document.getElementById('page-loader');
    if (pageLoader) {
        pageLoader.classList.add('hide');
        setTimeout(() => {
            if (pageLoader.parentNode) {
                pageLoader.parentNode.removeChild(pageLoader);
            }
        }, 500);
    }
});

// 备用：确保加载器在一定时间后隐藏
setTimeout(() => {
    const pageLoader = document.getElementById('page-loader');
    if (pageLoader) {
        pageLoader.classList.add('hide');
        setTimeout(() => {
            if (pageLoader.parentNode) {
                pageLoader.parentNode.removeChild(pageLoader);
            }
        }, 500);
    }
}, 3000); // 3秒后强制隐藏

// 导出类
window.ScrollAnimations = ScrollAnimations;
window.ParallaxEffect = ParallaxEffect;
window.ScrollProgress = ScrollProgress;
window.PageLoader = PageLoader;