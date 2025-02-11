$(document).ready(function() {
    // Initialize syntax highlighting
    hljs.highlightAll();

    // Copy button functionality
    $('.copy-btn').click(function() {
        const text = $(this).siblings('pre').text();
        navigator.clipboard.writeText(text);
        
        const btn = $(this);
        btn.text('Copied!');
        setTimeout(() => btn.text('Copy'), 2000);
    });

    // Add smooth scrolling to nav links
    $('a[href^="#"]').on('click', function(e) {
        e.preventDefault();
        const target = $(this.hash);
        if (target.length) {
            $('html, body').animate({
                scrollTop: target.offset().top - 70
            }, 500);
        }
    });

    // Add copy buttons to all code blocks
    $('pre code').each(function() {
        const btn = $('<button class="copy-btn">Copy</button>');
        $(this).parent().before(btn);
    });

    // Add language detection for code blocks
    $('pre code').each(function() {
        const text = $(this).text();
        if (text.includes('curl')) {
            $(this).addClass('language-bash');
        } else if (text.includes('{') || text.includes('[')) {
            $(this).addClass('language-json');
        }
    });

    // Search functionality
    $('#endpoint-search').on('input', function() {
        const query = $(this).val().toLowerCase();
        
        // Only filter if there's a search query
        if (query.length > 0) {
            $('.endpoint').each(function() {
                const endpoint = $(this);
                const title = endpoint.find('h3').text().toLowerCase();
                const path = endpoint.find('.path').text().toLowerCase();
                const description = endpoint.find('.description').text().toLowerCase();
                const method = endpoint.find('.method').text().toLowerCase();
                
                if (title.includes(query) || 
                    path.includes(query) || 
                    description.includes(query) || 
                    method.includes(query)) {
                    endpoint.show();
                } else {
                    endpoint.hide();
                }
            });
        } else {
            // If search is empty, show all endpoints (respecting current method filter)
            const activeMethod = $('.method-filter.active').data('method');
            filterByMethod(activeMethod);
        }
    });

    // Method filtering
    function filterByMethod(method) {
        if (method === 'all') {
            $('.endpoint').show();
        } else if (method === 'ws') {
            $('.endpoint').each(function() {
                const hasWebSocket = $(this).find('.method.websocket').length > 0;
                $(this).toggle(hasWebSocket);
            });
        } else {
            $('.endpoint').each(function() {
                const endpointMethod = $(this).find('.method').text().toLowerCase();
                $(this).toggle(endpointMethod === method);
            });
        }
    }

    $('.method-filter').click(function() {
        // Update active state
        $('.method-filter').removeClass('active');
        $(this).addClass('active');

        // Get selected method
        const method = $(this).data('method');
        
        // Apply filtering
        filterByMethod(method);
        
        // Also apply current search if there is one
        const searchQuery = $('#endpoint-search').val();
        if (searchQuery) {
            $('#endpoint-search').trigger('input');
        }
    });

    // Add dark mode toggle
    $('#dark-mode-toggle').click(function() {
        $('body').toggleClass('dark-mode');
        const isDark = $('body').hasClass('dark-mode');
        localStorage.setItem('darkMode', isDark);
    });

    // Check for saved dark mode preference
    if (localStorage.getItem('darkMode') === 'true') {
        $('body').addClass('dark-mode');
    }

    // Add response example toggle
    $('.toggle-response').click(function() {
        const example = $(this).siblings('.response-example');
        example.slideToggle();
        $(this).text(example.is(':visible') ? 'Hide Response' : 'Show Response');
    });

    // Add request example toggle
    $('.toggle-request').click(function() {
        const example = $(this).siblings('.curl-example');
        example.slideToggle();
        $(this).text(example.is(':visible') ? 'Hide Example' : 'Show Example');
    });

    // Add endpoint collapsing
    $('.endpoint h3').click(function() {
        const content = $(this).siblings();
        content.slideToggle();
        $(this).toggleClass('collapsed');
    });

    // Add keyboard shortcuts
    $(document).keydown(function(e) {
        // Ctrl/Cmd + K to focus search
        if ((e.ctrlKey || e.metaKey) && e.keyCode === 75) {
            e.preventDefault();
            $('#endpoint-search').focus();
        }
    });
}); 