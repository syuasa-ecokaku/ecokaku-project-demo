"""Exclude new notices and decorative count units from legacy department UI comparisons."""
def content_text(locator):
    return locator.evaluate("""e=>{
      const cards=[...e.querySelectorAll('.nc-card,.dk-unit')], previous=cards.map(c=>c.getAttribute('style'));
      try { cards.forEach(c=>c.style.setProperty('display','none','important')); return e.innerText; }
      finally { cards.forEach((c,i)=>previous[i]===null?c.removeAttribute('style'):c.setAttribute('style',previous[i])); }
    }""")
