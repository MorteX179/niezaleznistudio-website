function renderCard(item)
{
  var card = document.createElement('div');
  card.className = 'card';
  if(item.image)
  {
    card.style.backgroundImage = 'url("'+item.image+'")';
    card.classList.add('has-image');
  }
  var content = document.createElement('div');
  content.className = 'content';
  var title = document.createElement('h3');
  title.textContent = item.title || item.name || 'Brak tytułu';
  var desc = document.createElement('p');
  desc.className = 'muted';
  desc.textContent = item.desc || '';
  content.appendChild(title);
  content.appendChild(desc);
  card.appendChild(content);
  return card;
}

function loadAndRender(path, gridId, moreId, folderUrl)
{
  fetch(path).then(function(r)
  {
    if(!r.ok) throw new Error('no');
    return r.json();
  }).then(function(list)
  {
    if(!Array.isArray(list) || list.length===0) return;
    var grid = document.getElementById(gridId);
    for(var i=0;i<Math.min(3,list.length);i++)
    {
      var item = list[i];
      var a = document.createElement('a');
      a.href = (folderUrl||'') + (item.name || '#');
      a.style.textDecoration = 'none';
      var card = renderCard(item);
      a.appendChild(card);
      grid.appendChild(a);
    }
    if(list.length>3)
    {
      var more = document.getElementById(moreId);
      if(more)
      {
        more.style.display = 'block';
        var link = more.querySelector('a');
        if(link) link.href = folderUrl;
      }
    }
  }).catch(function()
  {
  });
}

document.addEventListener('DOMContentLoaded', function()
{
  loadAndRender('projekty/list.json','projGrid','projMore','projekty/');
  loadAndRender('zrealizowane/list.json','doneGrid','doneMore','zrealizowane/');
  var y = document.getElementById('year');
  if(y) y.textContent = new Date().getFullYear();
});
