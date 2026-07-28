(function (root, factory) {
  const exportsObject = factory(root);
  if (typeof module === 'object' && module.exports) {
    module.exports = exportsObject;
  }
  root.BuddySwitchMarkdownRenderer = exportsObject;
}(typeof globalThis !== 'undefined' ? globalThis : this, function (root) {
  'use strict';

  const SAFE_LINK_RE = /^(https?:\/\/|\/|#)/i;
  const SAFE_IMAGE_RE = /^https?:\/\//i;
  const ALLOWED_TAGS = [
    'a',
    'blockquote',
    'br',
    'code',
    'del',
    'div',
    'em',
    'h1',
    'h2',
    'h3',
    'h4',
    'h5',
    'h6',
    'hr',
    'img',
    'input',
    'li',
    'ol',
    'p',
    'pre',
    'span',
    'strong',
    'table',
    'tbody',
    'td',
    'th',
    'thead',
    'tr',
    'ul',
  ];
  const ALLOWED_ATTR = [
    'alt',
    'checked',
    'class',
    'decoding',
    'disabled',
    'href',
    'loading',
    'rel',
    'src',
    'target',
    'title',
    'type',
  ];

  function escapeHtml(value) {
    return String(value)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#039;');
  }

  function isSafeLinkHref(value) {
    return SAFE_LINK_RE.test(String(value || '').trim());
  }

  function isSafeImageSrc(value) {
    return SAFE_IMAGE_RE.test(String(value || '').trim());
  }

  function hasExternalHref(value) {
    return /^https?:\/\//i.test(String(value || '').trim());
  }

  function allowSanitizedAttribute(attrName) {
    return ALLOWED_ATTR.indexOf(String(attrName || '').toLowerCase()) !== -1;
  }

  function installSanitizerHooks(DOMPurify) {
    if (!DOMPurify || typeof DOMPurify.addHook !== 'function') {
      return;
    }
    if (DOMPurify.__buddySwitchMarkdownHooksInstalled) {
      return;
    }
    DOMPurify.addHook('afterSanitizeAttributes', function (node) {
      const tagName = String(node && node.tagName ? node.tagName : '').toUpperCase();
      if (tagName === 'A') {
        const href = node.getAttribute && node.getAttribute('href') ? node.getAttribute('href') : '';
        if (hasExternalHref(href)) {
          node.setAttribute('target', '_blank');
          node.setAttribute('rel', 'noopener noreferrer');
        } else {
          node.removeAttribute('target');
          node.removeAttribute('rel');
        }
      }
      if (tagName === 'INPUT' && node.classList && node.classList.contains('task-list-item-checkbox')) {
        node.setAttribute('type', 'checkbox');
        node.setAttribute('disabled', '');
      }
      if (tagName === 'IMG') {
        const src = node.getAttribute && node.getAttribute('src') ? node.getAttribute('src') : '';
        if (isSafeImageSrc(src)) {
          node.setAttribute('loading', 'lazy');
          node.setAttribute('decoding', 'async');
        }
      }
    });
    DOMPurify.__buddySwitchMarkdownHooksInstalled = true;
  }

  function normalizeFenceLanguage(info) {
    return String(info || '').trim().split(/\s+/)[0];
  }

  function createMarkdownIt(deps) {
    const MarkdownIt = deps.markdownIt || root.markdownit;
    const hljs = deps.hljs || root.hljs || null;
    if (typeof MarkdownIt !== 'function') {
      throw new Error('markdown-it is not loaded.');
    }

    const md = new MarkdownIt({
      html: false,
      linkify: true,
      breaks: false,
      typographer: false,
      langPrefix: 'language-',
      highlight(code, languageInfo) {
        const language = normalizeFenceLanguage(languageInfo);
        if (!language || !hljs || typeof hljs.getLanguage !== 'function' || !hljs.getLanguage(language)) {
          return escapeHtml(code);
        }
        try {
          if (typeof hljs.highlight === 'function') {
            return hljs.highlight(code, { language, ignoreIllegals: true }).value;
          }
        } catch (_error) {
          return escapeHtml(code);
        }
        return escapeHtml(code);
      },
    });

    md.validateLink = function () {
      return true;
    };
    installRendererRules(md);
    return md;
  }

  function installRendererRules(md) {
    const defaultLinkOpen = md.renderer.rules.link_open || function (tokens, idx, options, env, self) {
      return self.renderToken(tokens, idx, options);
    };
    md.renderer.rules.link_open = function (tokens, idx, options, env, self) {
      const token = tokens[idx];
      const href = token.attrGet('href') || '';
      if (!isSafeLinkHref(href)) {
        token.attrSet('href', '#');
      }
      if (hasExternalHref(token.attrGet('href'))) {
        token.attrSet('target', '_blank');
        token.attrSet('rel', 'noopener noreferrer');
      } else {
        token.attrSet('target', null);
        token.attrSet('rel', null);
      }
      return defaultLinkOpen(tokens, idx, options, env, self);
    };

    const defaultImage = md.renderer.rules.image || function (tokens, idx, options, env, self) {
      return self.renderToken(tokens, idx, options);
    };
    md.renderer.rules.image = function (tokens, idx, options, env, self) {
      const token = tokens[idx];
      const src = token.attrGet('src') || '';
      if (!isSafeImageSrc(src)) {
        return '';
      }
      token.attrSet('loading', 'lazy');
      token.attrSet('decoding', 'async');
      return defaultImage(tokens, idx, options, env, self);
    };

    md.renderer.rules.table_open = function () {
      return '<div class="markdown-table-wrap"><table>\n';
    };
    md.renderer.rules.table_close = function () {
      return '</table></div>\n';
    };
    md.renderer.rules.s_open = function () {
      return '<del>';
    };
    md.renderer.rules.s_close = function () {
      return '</del>';
    };
  }

  function addHighlightedCodeClass(html) {
    return html.replace(/<pre><code( class="([^"]*)")?>/g, function (_match, _classAttr, classes) {
      const classList = String(classes || '').split(/\s+/).filter(Boolean);
      if (classList.indexOf('hljs') === -1) {
        classList.unshift('hljs');
      }
      return '<pre><code class="' + classList.join(' ') + '">';
    });
  }

  function renderTaskLists(html) {
    const withItems = html.replace(/<li>(\s*)\[([ xX])\]\s+/g, function (_match, leading, marker) {
      const checked = marker.toLowerCase() === 'x' ? ' checked' : '';
      return '<li class="task-list-item">' + leading
        + '<input class="task-list-item-checkbox" type="checkbox" disabled' + checked + '> ';
    });
    return withItems.replace(/<ul>(\s*<li class="task-list-item")/g, '<ul class="task-list">$1');
  }

  function createMarkdownRenderer(deps) {
    const resolvedDeps = deps || {};
    const DOMPurify = resolvedDeps.DOMPurify || root.DOMPurify;
    if (!DOMPurify || typeof DOMPurify.sanitize !== 'function') {
      throw new Error('DOMPurify is not loaded.');
    }
    installSanitizerHooks(DOMPurify);
    const md = createMarkdownIt(resolvedDeps);
    return {
      renderMarkdownMessageHtml(content) {
        const rawHtml = renderTaskLists(addHighlightedCodeClass(md.render(String(content || ''))));
        return DOMPurify.sanitize(rawHtml, {
          ALLOWED_TAGS,
          ALLOWED_ATTR,
          ADD_TAGS: ALLOWED_TAGS,
          ADD_ATTR: allowSanitizedAttribute,
          ALLOWED_URI_REGEXP: SAFE_LINK_RE,
        });
      },
    };
  }

  let defaultRenderer = null;

  function renderMarkdownMessageHtml(content) {
    if (!defaultRenderer) {
      defaultRenderer = createMarkdownRenderer();
    }
    return defaultRenderer.renderMarkdownMessageHtml(content);
  }

  return {
    createMarkdownRenderer,
    renderMarkdownMessageHtml,
  };
}));
