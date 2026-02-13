fetch('list.json').then(r=>r.json()).then(list=>
{
  var g = document.getElementById('allGrid');
  list.forEach(function(item)
  {
    var a = document.createElement('a');
    a.href = item.name;
    a.style.textDecoration = 'none';
    var card = document.createElement('div');
    card.className = 'card';
    if(item.image) card.style.backgroundImage = 'url("'+item.image+'")';
    var content = document.createElement('div');
    content.className = 'content';
    var h = document.createElement('h3');
    h.textContent = item.title || item.name;
    var p = document.createElement('p');
    p.className = 'muted';
    p.textContent = item.desc || '';
    content.appendChild(h);
    content.appendChild(p);
    card.appendChild(content);
    a.appendChild(card);
    g.appendChild(a);
  });
}).catch(()=>{});
